import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from app.config import GOV_UK_SEARCH_MAX_COUNT
from app.database.db_operations import DbOperations
from app.database.table import async_db_session
from app.lib import logger

SEARCH_URL = "https://www.gov.uk/api/search.json"


class GovUKSearch:
    @staticmethod
    def build_search_url(
        query: str,
        count: int = 10,
        order_by_field_name: str = "",
        descending_order: bool = False,
        start: int = 0,
        fields: List[Optional[str]] = None,
        filter_by_field: List[Optional[Tuple[str, Any]]] = None,
        filter_any_field: List[Optional[Tuple[str, Any]]] = None,
        filter_all_fields: List[Optional[Tuple[str, Any]]] = None,
        reject_by_field: List[Optional[Tuple[str, Any]]] = None,
        reject_any_field: List[Optional[Tuple[str, Any]]] = None,
        reject_all_fields: List[Optional[Tuple[str, Any]]] = None,
        aggregate: List[Optional[Dict[str, Any]]] = None,
        ab_tests: Tuple[str, Any] = None,
        cachebust: bool = False,
    ) -> str:
        url = f"{SEARCH_URL}?q={query}"
        # count
        # maximum number of documents returned by the GOV UK API
        if count:
            url += f"&count={count}"
        # order
        if order_by_field_name != "" and not descending_order:
            url += f"&order={order_by_field_name}"
        if order_by_field_name != "" and descending_order:
            url += f"&order=-{order_by_field_name}"
        # start
        if start > 0:
            url += f"&start={start}"
        # fields
        # more than one field may be specified
        # field definitions: https://github.com/alphagov/search-api/blob/main/config/schema/field_definitions.json
        if fields:
            fields_list = [f"&fields={field}" for field in fields]
            url += f"{''.join(fields_list)}"
        # filter_*
        # more than one filter may be specified
        if filter_by_field:
            filter_list = [f"&filter_{f[0]}={f[1]}" for f in filter_by_field]
            url += f"{''.join(filter_list)}"
        # filter_any_*
        if filter_any_field:
            filter_any_field_list = [f"&filter_any_{f[0]}={f[1]}" for f in filter_any_field]
            url += f"{''.join(filter_any_field_list)}"
        # filter_all_*
        if filter_all_fields:
            filter_all_fields_list = [f"&filter_all_{f[0]}={f[1]}" for f in filter_all_fields]
            url += f"{''.join(filter_all_fields_list)}"
        # reject_*
        # more than one reject clauses may be specified
        if reject_by_field:
            rejected_by_fields_list = [f"&reject_{f[0]}={f[1]}" for f in reject_by_field]
            url += f"{''.join(rejected_by_fields_list)}"
        # reject_any_*
        if reject_any_field:
            reject_any_field_list = [f"&reject_any_{f[0]}={f[1]}" for f in reject_any_field]
            url += f"{''.join(reject_any_field_list)}"
        # reject_all_*
        if reject_all_fields:
            reject_all_field_list = [f"&reject_all_{f[0]}={f[1]}" for f in reject_all_fields]
            url += f"{''.join(reject_all_field_list)}"
        # aggregate_*
        if aggregate:
            for agg in aggregate:
                # aggregate_
                agg_str = "&aggregate_"
                # field
                agg_field = agg.get("field")
                if agg_field:
                    agg_str += f"{agg_field}"
                else:
                    raise ValueError("Gov UK Search API 'aggregate' field missin")
                # limit
                agg_limit = agg.get("limit")
                if agg_limit:
                    agg_str += f"={agg_limit}"
                else:
                    raise ValueError(f"Invalid Gov UK Search API 'aggregate' must have 'limit' set: {agg_limit}")
                # scope
                agg_scope = agg.get("scope")
                if agg_scope:
                    if agg_scope not in ["all_filters", "exclude_field_filter"]:
                        raise ValueError(f"Invalid Gov UK Search API 'aggregate' 'scope' value: {agg_scope}")
                    agg_str += f",scope:{agg.get('scope')}"
                # order
                agg_order = agg.get("order")
                if agg_order:
                    agg_str += ",order"
                    for order_item in agg_order:
                        if order_item not in [
                            "filtered",
                            "-filtered",
                            "count",
                            "-count",
                            "value",
                            "-value",
                            "value.slug",
                            "-value.slug",
                            "value.link",
                            "-value.link",
                            "value.title",
                            "-value.title",
                            "slug",
                            "-slug",
                        ]:
                            raise ValueError(f"Invalid Gov UK Search API 'aggregate' 'order' value: {order_item}")
                        agg_str += f":{order_item}"
                # examples
                agg_examples = agg.get("examples")
                if agg_examples:
                    agg_str += f",examples:{agg_examples}"
                # example_scope
                agg_example_scope = agg.get("example_scope")
                if agg_example_scope:
                    if agg_example_scope not in ["global", "query"]:
                        raise ValueError(
                            f"Invalid Gov UK Search API 'aggregate' 'example_scope' value: {agg_example_scope}"
                        )
                    agg_str += f",example_scope:{agg_example_scope}"
                # example_fields
                agg_example_fields = agg.get("example_fields")
                if agg_example_fields:
                    # 'example_fields' is added only when 'examples' is used
                    if agg_examples:
                        agg_str += f",example_fields:{agg_example_fields}"
        # ab_tests
        if ab_tests:
            url += f"&ab_tests={ab_tests[0]}:{ab_tests[1]}"
        # c - cachebust
        if cachebust:
            cachebust_str = str(datetime.datetime.now())
            url += f"&c={cachebust_str}"
        return url

    @staticmethod
    async def simple_search(
        query: str,
        count: int = GOV_UK_SEARCH_MAX_COUNT,
        order_by_field_name: str = "",
        descending_order: bool = False,
        start=0,
        fields: List[Optional[str]] = None,
        filter_by_field: List[Optional[Tuple[str, Any]]] = None,
        filter_any_field: List[Optional[Tuple[str, Any]]] = None,
        filter_all_fields: List[Optional[Tuple[str, Any]]] = None,
        reject_by_field: List[Optional[Tuple[str, Any]]] = None,
        reject_any_field: List[Optional[Tuple[str, Any]]] = None,
        reject_all_fields: List[Optional[Tuple[str, Any]]] = None,
        aggregate: List[Optional[Dict[str, Any]]] = None,
        ab_tests: Tuple[str, Any] = None,
        cachebust: bool = False,
        llm_internal_response_id_query: int = None,
    ) -> Tuple[Dict[str, Any], int]:
        get_url = GovUKSearch.build_search_url(
            query=query,
            count=count,
            order_by_field_name=order_by_field_name,
            descending_order=descending_order,
            start=start,
            fields=fields,
            filter_by_field=filter_by_field,
            filter_any_field=filter_any_field,
            filter_all_fields=filter_all_fields,
            reject_by_field=reject_by_field,
            reject_any_field=reject_any_field,
            reject_all_fields=reject_all_fields,
            aggregate=aggregate,
            ab_tests=ab_tests,
            cachebust=cachebust,
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(get_url) as response:
                response = await response.json()
                # Log the LLM-generated query passed on to the GOV UK Search API
                async with async_db_session() as db_session:
                    gov_uk_search_query = await DbOperations.insert_gov_uk_search_query(
                        db_session=db_session,
                        llm_internal_response_id=llm_internal_response_id_query,
                        query=query,
                    )

                logger.info(f"Queries built using tool use (function calling): {query}")

                return response, gov_uk_search_query
