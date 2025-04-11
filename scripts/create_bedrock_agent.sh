#!/bin/bash

set -e

# increase AGENT_SUFFIX when agent configuration has changed to create a new agent
# previous, unused agents then can be deleted via AWS Bedrock console.
AGENT_SUFFIX="agent1"

AWS_REGION=$1

SYSTEM_PROMPT=$(cat <<EOF
You are an AI assistant with access to a secure Python execution environment.
You can perform numerical calculations, data extraction, statistical analysis, and other Python-based computations.
You can process text and structured data, such as CSV, JSON, and Excel files, and provide insights using Python libraries.

When performing calculations or data analysis, first split the problem into steps, then clearly explain your approach and results in a concise manner.
If needed, first generate and execute Python code, capture the program execution output, and use the program output in building your analysis to ensure accuracy.
If a user requests an operation on an uploaded file, analyze the contents before providing a response.

In your chain of thought traces, include generated code, if applicable, so that I can verify numerical analysis if required.

Do not make assumptions, when numerical data is not provided by the user, state that you do not have information provided or tell the user what information is required to complete calculations.

Maintain efficiency by optimizing your computations and avoiding unnecessary processing.
Ensure security by adhering to best practices for safe code execution.
Do not execute arbitrary or potentially harmful commands outside the defined scope of your capabilities.
EOF
)


AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
EXECUTION_ROLE="arn:aws:iam::$AWS_ACCOUNT_ID:role/assist_bedrock_agent_admin_role"
FOUNDATION_MODEL="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EB_ENV_NAME=$(aws ec2 describe-tags --filters "Name=resource-id,Values=$INSTANCE_ID" --query "Tags[?Key=='elasticbeanstalk:environment-name'].Value" --output text)
AGENT_NAME="${EB_ENV_NAME}-${AGENT_SUFFIX}"

# Get agent ID
AGENT_ID=$(aws bedrock-agent list-agents --region "$AWS_REGION" --query "agentSummaries[?agentName=='$AGENT_NAME'].agentId | [0]" --output text)


if [[ -z "$AGENT_ID" || "$AGENT_ID" == "None" ]]; then
    echo "Creating new Bedrock agent: $AGENT_NAME"
    AGENT_ID=$(aws bedrock-agent create-agent \
        --region "$AWS_REGION" \
        --agent-name "$AGENT_NAME" \
        --agent-resource-role-arn "$EXECUTION_ROLE" \
        --foundation-model "$FOUNDATION_MODEL" \
        --instruction "${SYSTEM_PROMPT}" \
        --query 'agent.agentId' --output text)
    sleep 2

    echo "Enabling Code Interpreter"
    aws bedrock-agent create-agent-action-group \
      --agent-id "$AGENT_ID" \
      --agent-version "DRAFT" \
      --action-group-name "CodeInterpreterAction" \
      --parent-action-group-signature "AMAZON.CodeInterpreter" \
      --action-group-state "ENABLED" \
      --region "$AWS_REGION"

    echo "Enabling User Input"
    aws bedrock-agent create-agent-action-group \
      --agent-id "$AGENT_ID" \
      --agent-version "DRAFT" \
      --action-group-name "UserInputAction" \
      --parent-action-group-signature "AMAZON.UserInput" \
      --action-group-state "ENABLED" \
      --region "$AWS_REGION"

    echo "Preparing agent for usage"
    aws bedrock-agent prepare-agent --region "$AWS_REGION" --agent-id "$AGENT_ID"

    echo "Creating new agent alias"

      aws bedrock-agent create-agent-alias \
      --agent-alias-name "${AGENT_NAME}" \
      --agent-id "$AGENT_ID" \
      --region "$AWS_REGION"

echo "Bedrock agent setup complete."
else
  echo "Bedrock agent ${AGENT_NAME} is present, skipping agent setup"
fi
