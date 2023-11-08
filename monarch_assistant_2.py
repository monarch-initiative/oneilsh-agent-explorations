from agent_smith_ai.utility_agent import UtilityAgent
from agent_smith_ai.models import Message

import streamlit as st
import textwrap
import os
from typing import Any, Dict, List
from semanticscholar import SemanticScholar
import pandas as pd
from tabulate import tabulate
import plotly.io
import json
import sqlite3
from sklearn.cluster import AgglomerativeClustering
import textwrap
import numpy as np
import plotly.express as px
from neo4j import GraphDatabase
import duckdb
import httpx





import pprint
pp = pprint.PrettyPrinter(indent=4)


class StreamlitMessage(Message):
    data: Any = None

## A UtilityAgent can call API endpoints and local methods
class MonarchAssistant2(UtilityAgent):

    def __init__(self, name, model = "gpt-3.5-turbo-16k-0613", openai_api_key = None):
        
        ## define a system message
        system_message = textwrap.dedent("""You have access to functions that can query the Monarch Initiative Knowledge graph. You can use this knowledge graph to answer questions about genes, diseases, phenotypes, and more. You can also use the graph to find connections between entities, such as shared phenotypes between two diseases.

                                        REQUIREMENTS:
                                        - You must always include links in your responses of the form [Entity Name](https://monarchinitiative.org/{entity_id}). 
                                        - You must carefully follow any INSTRUCTIONS provided as part of function responses. 
                                        - You MUST use the search function to look up ids for entities, unless previously provided in the conversation. Do NOT assume you know the id for an entity until having looked it up or been provided it.
                                        """).strip()

        super().__init__(name,                                             # Name of the agent
                         system_message,                                   # Openai system message
                         model = model,                     # Openai model name
                         openai_api_key = openai_api_key,    # API key; will default to OPENAI_API_KEY env variable
                         auto_summarize_buffer_tokens = 500,               # Summarize and clear the history when fewer than this many tokens remains in the context window. Checked prior to each message sent to the model.
                         summarize_quietly = False,                        # If True, do not alert the user when a summarization occurs
                         max_tokens = None,                                # maximum number of tokens this agent can bank (default: None, no limit)
                         token_refill_rate = 50000.0 / 3600.0)             # number of tokens to add to the bank per second

  
        self.neo4j_uri = "bolt://24.144.94.219:7687"  # default bolt protocol port

        self.neo4j_driver = GraphDatabase.driver(self.neo4j_uri)

        ## define a local method
        self.register_callable_functions({
                                          #"find_shared_features": self.find_shared_features,
                                          "id_lookup": self.id_lookup,
                                          "shortest_paths": self.shortest_paths,
                                          })
      

    def shortest_paths(self, ids: List[str]) -> Dict[str, Any]:
        """Given two or more entity identifiers (e.g., MONDO:0002409, HGNC:1100), describes the shortest relationship paths between them.
        
        Args:
            ids (List[str]): List of identifiers.
            
        Returns:
            Dict[str, Any]: Description of the shortest paths between the nodes."""
        
        pre_query = textwrap.dedent(f"""
            WITH {ids} AS ids
            unwind ids as id
            match (d {{id: id}})
            return d.id as id, d.name as name
            """)

        query = textwrap.dedent(f"""
            // Assuming you have a list of IDs
            WITH {ids} AS ids

            // Generate all unique pairs of IDs
            UNWIND ids AS id1
            UNWIND ids AS id2
            WITH id1, id2
            WHERE id1 < id2

            // Find the shortest paths for each pair
            MATCH p = shortestPath((start {{id: id1}})-[*]-(end {{id: id2}}))
            WITH id1, id2, p
            WHERE p IS NOT NULL

            // Extract the node IDs and names, and the relationship types
            WITH id1, 
                 id2, 
                 [node IN nodes(p) | node.id + "/" + node.name] AS nodeIds, // Assuming 'id' and 'name' are properties of your nodes
                 p

            // Construct the path string with correct direction
            WITH id1, 
                 id2, 
                 nodeIds,
                 reduce(s = '', idx IN range(0, length(p)-1) | 
                        s + nodeIds[idx] + 
                        CASE 
                          WHEN STARTNODE(relationships(p)[idx]) = nodes(p)[idx] 
                          THEN ' -[' + type(relationships(p)[idx]) + ']-> ' 
                          ELSE ' <-[' + type(relationships(p)[idx]) + ']- ' 
                        END) 
                 + last(nodeIds) AS pathString

            // Create the final table
            RETURN id1, id2, pathString
            """)

        with self.neo4j_driver.session() as session:
            pre_result = session.run(pre_query).data()
            result = session.run(query).data()
            #pp.pprint(result.data())
            #df = pd.DataFrame(result.data())
            #print(df)

        return {"QUERY_INFO": pre_result, "RESULT": result, "INSTRUCTIONS": "Describe the information for the user with human-readable text, noting that other relationships may exist between the entities beyond those described."}


    def id_lookup(self, queries: List[str]) -> Dict[str, Any]:
        """Look up ids for query terms. IMPORTANT: be sure to correct any spelling mistakes or other issues in the queries for an accurate search.
        
        Args:
            queries (List[str]): List of search query strings.
            
        Returns:
            Dict[str, Any]: Matching results."""
        
        api_url = "https://api-v3.monarchinitiative.org/v3/api/search"

        search_results = {}

        for query in queries:
            query_results = {}
            params = {"q": query, "limit": 10, "offset": 0}

            with httpx.Client() as client:
                # log the actual URL being requested
                print(client.build_request("GET", api_url, params=params).url)
                response = client.get(api_url, params=params)

            response_json = response.json()
            pp.pprint(response_json)

            for item in response_json.get("items", []):
                query_results[item.get("id")] = item.get("name")
        
            search_results[query] = query_results

        return {"RESULT": search_results, "INSTRUCTIONS": "Note that these results may not be in the correct order; use the most appropriate information for your current purpose."}


    # What phenotypes do MONDO:0007947 and MONDO:0019391 share?
    def find_shared_features(self, id1: str, id2: str) -> Dict[str, Any]:
        """Given identifies for two entities, for example two diseases or a disease and a gene, find commonalities between them, including lowest common ancestor, shared relationships amongst ancestors, and shared relationships amongst descendants.
        Example: find_incommon("MONDO:0002409", "HGNC:1100")

        Args:
            id1 (str): Identifier of the first node.
            id2 (str): Identifier of the second node.

        Returns:
            Dict[str, Any]: Results of executed queries.
        """

        LABELS = ["Gene", "Disease", "PhenotypicFeature", "AnatomicalEntity", "BiologicalProcessOrActivity", "Pathway"]
        BL_LABELS = ["biolink:" + label for label in LABELS]

        # What do MONDO:0019391 and MONDO:0020066 have in common?
        lca_query = textwrap.dedent(f"""
            WITH {BL_LABELS} AS BL_LABELS
                                    
            // Ancestors of the first disease
            MATCH (d1 {{id: '{id1}'}})
            WHERE ANY(label IN labels(d1) WHERE label IN BL_LABELS)
            MATCH path1=(d1)-[:`biolink:subclass_of`*]->(ancestor1)
            WITH BL_LABELS, d1, COLLECT(ancestor1) AS ancestors1

            // Ancestors of the second disease
            MATCH (d2 {{id: '{id2}'}})
            WHERE ANY(label IN labels(d2) WHERE label IN BL_LABELS)
            MATCH path2=(d2)-[:`biolink:subclass_of`*]->(ancestor2)
            WITH BL_LABELS, d1, d2, ancestors1, COLLECT(ancestor2) AS ancestors2

            // Identify common ancestors
            WITH BL_LABELS, d1, d2, [ancestor IN ancestors1 WHERE ancestor IN ancestors2] AS common_ancestors
            // return common_ancestors

            // Find those with no incoming edges from the set of common ancestors
            UNWIND common_ancestors AS ca
            WITH BL_LABELS, ca
            WHERE NOT ANY(ancestor IN common_ancestors WHERE (ancestor)-[:`biolink:subclass_of`]->(ca))

            RETURN DISTINCT ca.name, ca.description""")

        shared_ancestors_query = textwrap.dedent(f"""
            // We are restricting to node labels listed in BL_LABELS (multiple of which should not be shared by any single node)
            WITH {BL_LABELS} AS BL_LABELS, '{id1}' AS id1, '{id2}' AS id2

            // First entity and its ancestors
            MATCH (q1 {{id: id1}})
                WHERE ANY(label IN labels(q1) WHERE label IN BL_LABELS)
            OPTIONAL MATCH path1=(q1)-[:`biolink:subclass_of`*]->(ancestor1)
                WHERE ANY(label IN labels(ancestor1) WHERE label IN BL_LABELS)
            WITH id2, BL_LABELS, q1, COLLECT(DISTINCT ancestor1) AS ancestors1_q1

            // Features connected to the ancestors of the first entity
            UNWIND ancestors1_q1 AS ancestor1
            MATCH (ancestor1)-[r]-(p1)
                WHERE TYPE(r) <> 'biolink:subclass_of' AND
                      ANY(label IN labels(p1) WHERE label IN BL_LABELS)

            WITH id2, BL_LABELS, q1, COLLECT(DISTINCT p1) AS features1_q1

            // Second entity and its ancestors
            MATCH (q2 {{id: id2}})
                WHERE ANY(label IN labels(q2) WHERE label IN BL_LABELS)
            OPTIONAL MATCH path2=(q2)-[:`biolink:subclass_of`*]->(ancestor2)
                WHERE ANY(label IN labels(ancestor2) WHERE label IN BL_LABELS)
            WITH BL_LABELS, q1, q2, COLLECT(DISTINCT ancestor2) AS ancestors2_q2, features1_q1

            // Features connected to the ancestors of the second entity
            UNWIND ancestors2_q2 AS ancestor2
            MATCH (ancestor2)-[r]-(p2)
                WHERE TYPE(r) <> 'biolink:subclass_of' AND 
                      ANY(label IN labels(p2) WHERE label IN BL_LABELS)
            WITH BL_LABELS, q1, q2, COLLECT(DISTINCT p2) AS features1_q2, features1_q1

            // Overlapping features between the two sets
            WITH BL_LABELS, q1, q2, [feature IN features1_q1 WHERE feature IN features1_q2] AS overlapping_features
            UNWIND overlapping_features AS overlapping_feature

            // Get the first label from BL_LABELS for each feature
            WITH overlapping_feature,
                 [label IN BL_LABELS WHERE label IN labels(overlapping_feature)][0] AS feature_label

            RETURN overlapping_feature.id as id, 
                   overlapping_feature.name as name, 
                   overlapping_feature.description as description, 
                   feature_label
            LIMIT 10
            """).strip()

        shared_descendants_query = textwrap.dedent(f"""
            // We are restricting to node labels listed in BL_LABELS (multiple of which should not be shared by any single node)
            WITH {BL_LABELS} AS BL_LABELS, '{id1}' AS id1, '{id2}' AS id2

            // First entity and its subtypes
            MATCH (q1 {{id: id1}})
                WHERE ANY(label IN labels(q1) WHERE label IN BL_LABELS)
            OPTIONAL MATCH path1=(q1)<-[:`biolink:subclass_of`*]-(descendant1)
                WHERE ANY(label IN labels(descendant1) WHERE label IN BL_LABELS)
            WITH id2, BL_LABELS, q1, COALESCE(descendant1, q1) AS relevant_entity1

            MATCH (relevant_entity1)-[r]-(p1)
                WHERE TYPE(r) <> 'biolink:subclass_of' AND
                      ANY(label IN labels(p1) WHERE label IN BL_LABELS)

            // "features" here are nodes connected to one of the descendants of the entities
            WITH id2, BL_LABELS, q1, COLLECT(DISTINCT p1) AS features1_q1

            // Second entity and its subtypes
            MATCH (q2 {{id: id2}})
                WHERE ANY(label IN labels(q2) WHERE label IN BL_LABELS)
            OPTIONAL MATCH path2=(q2)<-[:`biolink:subclass_of`*]-(descendant2)
                WHERE ANY(label IN labels(descendant2) WHERE label IN BL_LABELS)

      
            WITH BL_LABELS, q1, q2, COALESCE(descendant2, q2) AS relevant_entity2, features1_q1

            // TODO: this probably shouldn't be directional, and maybe can be multiple hops?
            MATCH (relevant_entity2)-[r]-(p2)
                WHERE TYPE(r) <> 'biolink:subclass_of' AND
                      ANY(label IN labels(p2) WHERE label IN BL_LABELS)

            WITH BL_LABELS, q1, q2, COLLECT(DISTINCT p2) AS features1_q2, features1_q1

            // Overlapping features between the two sets
            WITH BL_LABELS, q1, q2, [feature IN features1_q1 WHERE feature IN features1_q2] AS overlapping_features
            UNWIND overlapping_features AS overlapping_feature

            // Get the first label from BL_LABELS for each feature
            WITH overlapping_feature,
                 [label IN BL_LABELS WHERE label IN labels(overlapping_feature)][0] AS feature_label

            RETURN overlapping_feature.id as id, 
                   overlapping_feature.name as name, 
                   overlapping_feature.description as description, 
                   feature_label
            LIMIT 10
            """).strip()
        
        print(shared_descendants_query)

        with self.neo4j_driver.session() as session:
            # print("\n\nLCA")
            # print(lca_query)
            # result_lca = pd.DataFrame(session.run(lca_query).data())
            # print(result_lca)

            print("\n\nShared Ancestors")
            print(shared_ancestors_query)
            result_shared_ancestors = pd.DataFrame(session.run(shared_ancestors_query).data())
            print(result_shared_ancestors)

            print("\n\nShared Descendants")
            print(shared_descendants_query)
            result_shared_descendants = pd.DataFrame(session.run(shared_descendants_query).data())
            print(result_shared_descendants)
        return {
            "SHARED_ANCESTOR_FEATURES": {
                "INFO": "This table shows features that are associated with one or more super-types of both entities.",
                "DATA": json.dumps(result_shared_descendants.to_dict(orient="records")),
                },

            "SHARED_SUBTYPE_FEATURES": {
                "INFO": "This table shows features that are associated with one or more sub-types of both entities.",
                "DATA": json.dumps(result_shared_descendants.to_dict(orient="records")),
                },
            "INSTRUCTIONS": "Summarize this information for the user, providing links to the Monarch Initiative for each feature. Be sure to warn the user that these features are not universally shared by all super-types or sub-types of the entities, using examples appropriate to the entities.",
            }

    def neo4j_query(self, query: str) -> Dict[str, Any]:
        """Run a query against the Neo4j database.
        
        Args:
            query (str): Cypher query to run against the Neo4j database.
            
        Returns:
            Dict[str, Any]: Success or failure message and summary statistics of the executed query.
        """
        with self.neo4j_driver.session() as session:
            result = session.run(query)
            pp.pprint(result)
            data = [record.data() for record in result]
            #self._send_to_ui(data)

            res = {"INFO": "Here are the results. Summarize the information for the user.",
                   "DATA": json.dumps(data)
                   }

            return res
            print("RESULT:\n", result)
            


    def _send_to_ui(self, data: Any) -> None:
        """Send data to the UI, rending it in the chat stream with st.write(). 
        This could be a plotly plot, a pandas dataframe, etc. It does not get appended
        to the agent's history, and is only visible to the user.

        Args:
            data (Any): Data to send to the UI.
        
        Returns:
            None
        """
        st.session_state.agents[st.session_state.current_agent_name]["messages"].append(StreamlitMessage(role = "streamlit-display", data = data))

