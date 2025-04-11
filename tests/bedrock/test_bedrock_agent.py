from unittest.mock import patch

import pytest

from app.services.bedrock.bedrock_agent import BedrockAgentClient
from app.services.bedrock.bedrock_types import BedrockError
from app.types.chat_agent import AgentFinalResponse


@pytest.mark.asyncio
@patch("app.services.bedrock.bedrock_agent.boto3")
@patch("app.services.bedrock.bedrock_agent._get_agent_id_by_name")
@patch("app.services.bedrock.bedrock_agent._get_alias_id_by_name")
async def test_bedrock_agent_stream_success(mock_agent_alias, mock_agent_id, mock_boto):
    agent = BedrockAgentClient.get("test-agent", "test-region")

    _invoke_agent = {
        "completion": [
            {"chunk": {"bytes": b"text1"}},
            {"chunk": {"bytes": b"text2"}},
            {"chunk": {"bytes": b"text3"}},
            {
                "trace": {
                    "trace": {
                        "orchestrationTrace": {
                            "modelInvocationOutput": {
                                "traceId": "trace1",
                                "metadata": {"usage": {"inputTokens": 100, "outputTokens": 10}},
                            }
                        }
                    }
                }
            },
            {
                "trace": {
                    "trace": {
                        "orchestrationTrace": {
                            "modelInvocationOutput": {
                                "traceId": "trace2",
                                "metadata": {"usage": {"inputTokens": 110, "outputTokens": 20}},
                            }
                        }
                    }
                }
            },
        ]
    }

    mock_boto.client.return_value.invoke_agent.return_value = _invoke_agent

    async def _on_complete(final_response: AgentFinalResponse):
        assert final_response.final_response == "text1text2text3"
        assert final_response.total_input_tokens == 210
        assert final_response.total_output_tokens == 30

    response = agent.call_agent(text="Explain me PI in math", session_id="session-id", on_complete=_on_complete)

    async for reply in response:
        print(reply)


@pytest.mark.parametrize(
    ("exception_type"),
    [
        "internalServerException",
        "conflictException",
        "dependencyFailedException",
        "modelNotReadyException",
        "resourceNotFoundException",
    ],
)
@pytest.mark.asyncio
@patch("app.services.bedrock.bedrock_agent.boto3")
@patch("app.services.bedrock.bedrock_agent._get_agent_id_by_name")
@patch("app.services.bedrock.bedrock_agent._get_alias_id_by_name")
async def test_bedrock_agent_stream_fail(mock_agent_alias, mock_agent_id, mock_boto, exception_type):
    agent = BedrockAgentClient.get("test-agent-2", "test-region-2")

    _invoke_agent = {"completion": [{exception_type: {"message": f"Error {exception_type} occurred"}}]}

    mock_boto.client.return_value.invoke_agent.return_value = _invoke_agent

    async def _on_complete(final_response: AgentFinalResponse):
        pytest.fail("Should not run on_complete")

    with pytest.raises(BedrockError) as e:
        response = agent.call_agent(text="Explain me PI in math", session_id="session-id", on_complete=_on_complete)
        async for _ in response:
            assert str(e) == f"{exception_type}: Error {exception_type} occurred"
