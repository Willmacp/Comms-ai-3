SEARCH_API_SEARCH_TERMS = {
    "tools": [
        {
            "name": "call_gov_uk_search_api",
            "description": (
                "Calls GOV UK Search API with a list of search terms that best match the user query. "
                "These search terms may be keywords, e.g. 'taxes' or phrases 'personal tax rates'. "
                "The search terms derived from the context of the user query ought to be a list of "
                "strings in JSON format."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "search_terms": {
                        "type": "array",
                        "items": {"type": "string", "description": "a search term"},
                    }
                },
                "required": ["search_terms"],
            },
        }
    ]
}

DOCUMENT_RELEVANCE_ASSESSMENT = {
    "tools": [
        {
            "name": "assess_document_relevance",
            "description": """
                This tool assesses document relevancy to the given query.
                I would like you analyse the title and content of the document. Answer 'True' if the document is
                highly relevant to the query I am going to give you below; otherwise answer 'False'.

                Be very strict with your assessment. In particular, pay attention to the title of the Gov UK page.
                Discard any pages that are clearly login pages,or pages that only exist to let you download document.
                """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "is_relevant": {
                        "type": "boolean",
                    }
                },
                "required": ["is_relevant"],
            },
        }
    ]
}

DOWNLOAD_URLS = {
    "tools": [
        {
            "name": "download_urls",
            "description": """
                This tool downloads documents using URLs found in the user query.
                """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string", "description": "URL"},
                    }
                },
                "required": ["urls"],
            },
        }
    ]
}
