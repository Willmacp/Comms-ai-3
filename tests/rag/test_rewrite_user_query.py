from unittest.mock import MagicMock, patch

import pytest

from app.services.rag.rewrite_user_query import rewrite_user_query


@pytest.mark.asyncio
@patch("app.services.rag.rewrite_user_query.async_db_session")
async def test_opensearch_system_prompt_generates_plaintext_queries(async_db_session, caplog):
    """
    Tests LLM generated opensearch query items text queries usable in OpenSearch search API.

    Asserts:
        - Query rewriter returns an array object
        - Each item in the returned array is a text query.
    """

    opensearch_system_prompt_new = (
        "You work for members of GCS (the Government Communication Service) "
        "which is part of the UK Civil Service. Your job is to rewrite the users query so "
        "it can be used in the query body for OpenSearch to retrieve relevant information. "
        "The next message you receive will be the users original query. You should only "
        "respond with an unlabelled JSON array of a variety of three queries that are "
        "rewritten for maximum effect with OpenSearch. Each array item must be a plain "
        "text query, and it can have logical operators to improve search match."
    )

    llm = MagicMock()
    llm.id = 1
    system_prompt = MagicMock()
    system_prompt.id = 1
    system_prompt.content = opensearch_system_prompt_new

    user_query = (
        "The UK has long been a leader in DNA research and biotechnology, with numerous universities and "
        "research institutions at the forefront of genetic discoveries. British scientists and biotech "
        "companies have contributed significantly to the development of gene editing techniques, including "
        "CRISPR, which has the potential to revolutionize the treatment of genetic diseases. "
        "These advancements have allowed researchers to explore the possibility of correcting genetic "
        "mutations at their source, offering hope for the treatment of conditions such as cystic fibrosis, "
        "muscular dystrophy, and certain app_types of cancer.) Beyond medicine, UK-based biotech companies are "
        "also exploring the use of DNA technologies in agriculture, environmental science, and synthetic "
        "biology. For example, genetic modification techniques are being used to develop crops that are more "
        "resistant to diseases and adverse environmental conditions. The UK’s biotech sector continues "
        "to thrive, driven by strong academic collaborations, government funding, and a well-established "
        "regulatory framework that promotes innovation while ensuring ethical standards are met. "
        "The UK has been at the forefront of regulating genetic modification, including the use of CRISPR "
        "technology for both research and medical purposes. CRISPR, a gene-editing technology that allows "
        "scientists to modify DNA with unprecedented precision, has raised ethical and regulatory concerns, "
        "particularly regarding its use in human embryos. In the UK, the Human Fertilisation and "
        "Embryology Authority (HFEA) strictly regulates research involving human embryos, ensuring that "
        "genetic modification is conducted within ethical boundaries and for legitimate medical purposes."
        "In agriculture, the UK also has stringent laws governing the use of genetically modified organisms "
        "(GMOs). While GMOs have the potential to address food security challenges by producing crops "
        "that are more resistant to pests and environmental changes, there is ongoing public debate about "
        "their safety and environmental impact. The UK government continues to monitor these developments "
        "closely, and future legislation will likely address emerging technologies, such as gene drives, "
        "that could have far-reaching implications for both human health and the environment."
    )

    search_index = MagicMock()
    user_message = MagicMock()
    result = await rewrite_user_query(user_query, search_index, user_message, llm, system_prompt)

    # check no errors in generated queries
    assert "No valid rewritten queries found. Using original user message." not in caplog.text

    # Assert all queries are text
    assert all(isinstance(item, str) for item in result)

    # Assert no db interactions.
    async_db_session.assert_called()
