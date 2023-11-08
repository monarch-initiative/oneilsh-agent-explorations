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
class SemanticScholarAgent(UtilityAgent):

    def __init__(self, name, model = "gpt-3.5-turbo-16k-0613", openai_api_key = None):
        
        ## define a system message
        system_message = textwrap.dedent("""You are the Monarch Assistant, with access to the Monarch Initiative Knowledge graph, provided as
                                        access to a database.

                                        Node categories/labels are partly CamelCase, examples: `biolink:Disease`, `biolink:Gene`, `biolink:PhenotypicFeature`.
                                        Edge categories/relationship types are partly snake_case, examples: `biolink:has_phenotype`, `biolink:contributes_to`, `biolink:has_mode_of_inheritance`.

                                        Here are the top 15 most common relationships in the graph:
                                         
                                        240262   biolink:Disease                          biolink:has_phenotype                               biolink:PhenotypicFeature              
                                        38204    biolink:Disease                          biolink:subclass_of                                 biolink:Disease                        
                                        8411     biolink:Disease                          biolink:has_mode_of_inheritance                     biolink:PhenotypicFeature              
                                        7946     biolink:Gene                             biolink:gene_associated_with_condition              biolink:Disease                        
                                        6496     biolink:Gene                             biolink:causes                                      biolink:Disease                        
                                        2605     biolink:Disease                          biolink:related_to                                  biolink:GrossAnatomicalStructure       
                                        1584     biolink:Disease                          biolink:related_to                                  biolink:PhenotypicQuality              
                                        1449     biolink:Disease                          biolink:related_to                                  biolink:PhenotypicFeature              
                                        858      biolink:Disease                          biolink:related_to                                  biolink:Disease                        
                                        757      biolink:Disease                          biolink:related_to                                  biolink:NamedThing                     
                                        590      biolink:Gene                             biolink:contributes_to                              biolink:Disease                        
                                        441      biolink:Disease                          biolink:related_to                                  biolink:CellularOrganism               
                                        414      biolink:Disease                          biolink:related_to                                  biolink:AnatomicalEntity               
                                        391      biolink:Disease                          biolink:related_to                                  biolink:BiologicalProcessOrActivity    
                                        249      biolink:MolecularEntity                  biolink:affects                                     biolink:Disease                        

                                        All nodes have `id` and `name` properties, and most nodes have a `description` property. Gene nodes also have a `symbol` property.
                                         
                                        EXAMPLE QUERIES:
                                                                                 

                                        IMPORTANT: the `biolink:sublass_of` relationship indicates "type of" relationships. These should be used carefully and judiciously in queries to best answer the users' query. For example, if the user asks about genes related to a specific disease, you should also list genes related to sub-types of that disease, unless instructed otherwise.
                                        IMPORTANT: Do *not* assume you know the identifier for a node. Use the search_entity function to find the identifier for a node, and then use that identifier in your query.
                                        IMPORTANT: The results from search_entity are not optimally ordered - choose the most appropriate information from the results.
                                        """).strip()
        
                                        # - Diseases associated with a gene: MATCH (g:`biolink:Gene`{id:"HGNC:1100"})-[]-(d:`biolink:Disease`) RETURN g,d LIMIT 10
                                        # - Phenotypes associated with diseases associated with a gene: MATCH (g:`biolink:Gene`{id:"HGNC:1100"})-[]->(d:`biolink:Disease`)-[]->(p:`biolink:PhenotypicFeature`) RETURN g,d,p LIMIT 10
                                        # - Genes associated with a disease or any subclass of that disease: MATCH (d:`biolink:Disease`{id:"MONDO:0002409"})<-[:`biolink:subclass_of`*]-(d2:`biolink:Disease`)<-[`biolink:risk_affected_by`]-(g:`biolink:Gene`) RETURN d.id, d.name, d2.id, d2.name,g.symbol,g.id LIMIT 10                                         


        super().__init__(name,                                             # Name of the agent
                         system_message,                                   # Openai system message
                         model = model,                     # Openai model name
                         openai_api_key = openai_api_key,    # API key; will default to OPENAI_API_KEY env variable
                         auto_summarize_buffer_tokens = 500,               # Summarize and clear the history when fewer than this many tokens remains in the context window. Checked prior to each message sent to the model.
                         summarize_quietly = False,                        # If True, do not alert the user when a summarization occurs
                         max_tokens = None,                                # maximum number of tokens this agent can bank (default: None, no limit)
                         token_refill_rate = 50000.0 / 3600.0)             # number of tokens to add to the bank per second

        self.sch = SemanticScholar()

        #self.db = sqlite3.connect(":memory:")
        self.duckdb = duckdb.connect(database="monarch.duckdb", read_only=True)

        self.neo4j_uri = "bolt://24.144.94.219:7687"  # default bolt protocol port

        self.neo4j_driver = GraphDatabase.driver(self.neo4j_uri)


        ## define a local method
        self.register_callable_functions({#"search": self.search,
                                          #"sql_query_table": self.sql_query_table,
                                          #"load_demo_data": self.load_demo_data,
                                          #"plotly_dotplot": self.plotly_dotplot, 
                                          #"plotly_barplot": self.plotly_barplot, 
                                          #"pyvis_network_graph": self.pyvis_network_graph,
                                          #"neo4j_query": self.neo4j_query
                                          #"duckdb_query": self.duckdb_query,
                                          "find_shared_features": self.find_shared_features,
                                          "monarch_search_multi": self.monarch_search_multi,
                                          "shortest_paths": self.shortest_paths,
                                          #"recursive_summarize": self.recursive_summarize,
                                          })
      
        # self.register_api("monarch", 
        #                   spec_url = "https://oai-monarch-plugin.monarchinitiative.org/openapi.json", 
        #                   base_url = "https://oai-monarch-plugin.monarchinitiative.org",
        #                   callable_endpoints = ['search_entity'])


    def duckdb_query(self, query: str) -> Dict[str, Any]:
        """Run a query against the DuckDB database. Tables and columns:
        Table `nodes` columns: id, category, name, symbol, description
        Table `edges` columns: id, predicate, publications, subject, object
        
        You may need to generate complex queries using regular or recursive CTEs.
        

        The most important columns 

        Args:
            query (str): SQL query to run against the DuckDB database.

        Returns:
            Dict[str, Any]: Success or failure message and summary statistics of the executed query.
        """

        df = pd.read_sql_query(query, self.duckdb)

        res = {"INFO": "Here are the results. Summarize the information for the user.",
               "DATA": json.dumps(df.to_dict(orient="records"))
               }

        return res

    def system_test(self) -> Dict[str, Any]:
        """Runs a system test."""

        query = textwrap.dedent("""
                                MATCH (d:`biolink:Disease` {id:"MONDO:0002409"})<-[:`biolink:subclass_of`*]-(d2:`biolink:Disease`)<-[`biolink:risk_affected_by`]-(g:`biolink:Gene`) RETURN d.id, d.name, d2.id, d2.name,g.symbol,g.id LIMIT 10
                                """)
        
        with self.neo4j_driver.session() as session:
            result = session.run(query)
            df = pd.DataFrame(result.data())
            print(df)

        return {"RESULT": "Works!"}


    def shortest_paths(self, ids: List[str]) -> Dict[str, Any]:
        """Given a list of identifiers, find the shortest paths between all of them. Useful to search for connections between entities.
        
        Args:
            ids (List[str]): List of identifiers.
            
        Returns:
            Dict[str, Any]: Description of the shortest paths between the nodes."""
        
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
            result = session.run(query)
            df = pd.DataFrame(result.data())
            print(df)

        return {"RESULT": df.to_dict(orient="records")}

    def path_through_common(self, id1: str, id2: str, id_shared: str) -> Dict[str, Any]:
        """Finds and describes the shortest paths between id1 and id_shared, and id2 and id_shared. Can be used to discover how a given entity relates to two others.
        
        Args:
            id1 (str): Identifier of the first node.
            id2 (str): Identifier of the second node.
            id_shared (str): Identifier of the shared node.
            
        Returns:
            Dict[str, Any]: Description of the shortest paths between the three nodes."""
        
        query = textwrap.dedent(f"""
            WITH '{id1}' AS startId, '{id_shared}' AS throughId, '{id2}' AS endId

            // Find the shortest path from the start node to the 'through' node
            MATCH path1 = shortestPath((start {{id: startId}})-[*]-(through {{id: throughId}}))

            // Find the shortest path from the 'through' node to the end node
            MATCH path2 = shortestPath((through)-[*]-(end {{id: endId}}))

            WITH startId, throughId, endId, collect(path1) + collect(path2) AS paths

            // Unwind the paths to create a row for each path
            UNWIND paths AS path
            WITH startId, 
                 endId, 
                 [node IN nodes(path) | node.id + "/" + node.name] AS nodeIds, // Assuming 'id' is a property of your nodes
                 [rel IN relationships(path) | type(rel)] AS relTypes

            // Construct the path string
            WITH startId, 
                 endId, 
                 reduce(s = '', idx IN range(0, size(nodeIds)-2) | 
                        s + nodeIds[idx] + ' -[' + relTypes[idx] + ']-> ') + last(nodeIds) AS pathString

            // Create the final table
            RETURN startId, endId, pathString
            """).strip()

        with self.neo4j_driver.session() as session:
            result = session.run(query)
            df = pd.DataFrame(result.data())
            print(df)
        
        return {"RESULT": df.to_dict(orient="records")}


    def monarch_search_multi(self, queries: List[str]) -> Dict[str, Dict[str, str]]:
        """Keyword-based search for the Monarch Initiative. Returns a list of entities matching the query and their identifiers for further use. IMPORTANT: be sure to correct any spelling mistakes or other issues in the queries for an accurate search.
        
        Args:
            queries (List[str]): List of search queries.
            
        Returns:
            Dict[str, Dict[str, str]]: Results, broken out by query."""
        
        api_url = "https://api-v3.monarchinitiative.org/v3/api/search"

        search_results = {}

        for query in queries:
            query_results = {}
            params = {"q": query, "limit": 20, "offset": 0}

            with httpx.Client() as client:
                # log the actual URL being requested
                print(client.build_request("GET", api_url, params=params).url)
                response = client.get(api_url, params=params)

            response_json = response.json()
            pp.pprint(response_json)

            for item in response_json.get("items", []):
                query_results[item.get("id")] = item.get("name")
        
            search_results[query] = query_results

        return search_results

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
            
            # data = [record["connectedNode"].properties for record in result]
            # df = self._convert_lists_to_json(pd.DataFrame(data))

            # # df = self._convert_lists_to_json(pd.DataFrame(result.data()))

            # print("DF:\n", df)
            # df.to_sql("neo4j_results", self.db, if_exists="replace")

            # df_colnames = df.columns.tolist()

            # user_sample = self._query_db("SELECT * FROM neo4j_results LIMIT 5")
            # self._send_to_ui("<h4>Neo4j Results</h4>")
            # self._send_to_ui(user_sample)

            # res = {"INFO": "The user has been show the full results as a browsable table; here is a sample of results. Comprehensively summarize the information.",
            #        "COLUMNS": df_colnames,
            #        "TOTAL_ROWS": len(df),
            #        "SAMPLE_QUERY": query,
            #        "SAMPLE_RESULT": json.loads(df.head().to_json(orient="records")),
            #        }
            # return res

    def _convert_lists_to_json(self, df):
        for col in df.columns:
            if df[col].apply(type).eq(list).any():  # Check if any cell in column is a list
                df[col] = df[col].apply(json.dumps)  # Convert entire column to JSON strings
            # You can add more conditions here for other non-native SQLite types if needed.
        return df

    def _convert_json_to_lists(self, df):
        for col in df.columns:
            try:
                # Attempt to load the first non-null item in the column as JSON
                if pd.notna(df[col]).any() and isinstance(json.loads(df[col].dropna().iloc[0]), list):
                    df[col] = df[col].apply(json.loads)
            except json.JSONDecodeError:
                # If decoding fails, it's not a JSON serialized column, so move on
                continue
        return df



    def pyvis_network_graph(self,
                        nodes_id_col: str,
                        edge_source_id_col: str,
                        edge_dest_id_col: str,
                        directed: bool = False,
                        node_color_col: str = None,
                        node_text_col: str = None,
                        edge_text_col: str = None,
                        # title: str = None,
                        # node_color_title: str = None,
                        # color_continuous_scale: str = "Viridis",
                        nodes_sql_query: str = "<sql query to generate the nodes table>",
                        edges_sql_query: str = "<sql query to generate the edges table>",
                        ) -> Dict[str, Any]:
        """Create a network graph using pyvis, using the results of a query to populate the data.

        Args:
            nodes_id_col (str): Column to use for the node ids in the nodes table.
            edge_source_id_col (str): Column to use for the source node ids in the edges table.
            edge_dest_id_col (str): Column to use for the destination node ids in the edges table.
            directed (bool, optional): Whether the graph is directed or not. Defaults to False.
            node_color_col (str, optional): Column to use for the node color. Defaults to None.
            node_text_col (str, optional): Column to use for the node text. Defaults to None.
            edge_text_col (str, optional): Column to use for edge text. Defaults to None.
            nodes_sql_query (str, optional): SQL query to run against the in-memory database to generate the nodes table.
            edges_sql_query (str, optional): SQL query to run against the in-memory database to generate the edges table.

        Returns:
            Dict[str, Any]: Success or failure message and summary statistics of the executed query.
        """
        # nodes_df = self._query_db(nodes_sql_query)
        # edges_df = self._query_db(edges_sql_query)
        # print(nodes_df.head())
        # print(edges_df.head())
        # print(nodes_id_col)
        # print(edge_source_id_col)
        # print(edge_dest_id_col)


        # ## create the graph, cleanly handling cases where the user has not specified a color or text column
        # g = Network(directed=directed)
        # g.add_nodes(nodes_df[nodes_id_col].tolist(),
        #             )
        # g.add_edges(edges_df[[edge_source_id_col, edge_dest_id_col]].values.tolist(),
        #             )

        
        # ## set the graph options
        # g.options = {
        #     "nodes": {
        #         "color": {
        #             "highlight": {
        #                 "border": "red",
        #                 "background": "pink",
        #             },
        #         },
        #         "font": {
        #             "color": "white",
        #         },
        #     },
        #     "edges": {
        #         "color": {
        #             "inherit": "both",
        #         },
        #         "smooth": {
        #             "enabled": True,
        #         },
        #     },
        #     "physics": {
        #         "enabled": True,
        #         "barnesHut": {
        #             "gravitationalConstant": -8000,
        #             "centralGravity": 0.3,
        #             "springLength": 200,
        #             "springConstant": 0.04,
        #             "damping": 0.09,
        #             "avoidOverlap": 0.9,
        #         },
        #         "minVelocity": 0.75,
        #         "maxVelocity": 200.0,
        #         "solver": "barnesHut",
        #         "timestep": 0.5,
        #         "adaptiveTimestep": True,
        #     },
        #     "interaction": {
        #         "dragNodes": True,
        #         "dragView": True,
        #         "hideEdgesOnDrag": False,
        #         "hideNodesOnDrag": False,
        #         "hover": True,
        #         "hoverConnectedEdges": True,
        #         "keyboard": {
        #             "enabled": False,
        #             "speed": {
        #                 "x": 10,
        #                 "y": 10,
        #                 "zoom": 0.02,
        #             },
        #             "bindToWindow": True,
        #         },
        #         "multiselect": True,
        #         "navigationButtons": True,
        #         "selectable": True,
        #         "selectConnectedEdges": True,
        #         "tooltipDelay": 300,
        #         "zoomView": True,
        #     },
        # }

        ## show the graph
        
        import streamlit.components.v1 as components
        import networkx as nx
        from pyvis.network import Network

        ## example random graph:
        
        nt = Network("500px", "500px")
        nt.from_nx(nx.fast_gnp_random_graph(100, 0.1))

        self._send_to_ui(components.html(nt.html, height = 400))

        res = {"INFO": "The user has been show the plot, be sure to describe what they are seeing. DO NOT attempt to display the plot again.",
                "TOTAL_ROWS": len(nodes_df),
                "QUERY_SUMMARY_STATISTICS": json.loads(nodes_df.describe().to_json(orient="records")),
                }
        
        return res



    def load_demo_data(self) -> Dict[str, Any]:
        """Load demo data into the in-memory database.
        
        Returns:
            Dict[str, Any]: Success or failure message and summary statistics of the executed query.
        """
        df = pd.read_csv("mtcars.csv")
        df.to_sql("mtcars", self.db, if_exists="replace")

        sample_query = "SELECT * FROM mtcars LIMIT 5"
        sample_result = self._query_db(sample_query)

        res = {"INFO": "Demo data loaded into table 'mtcars'.",
               "TOTAL_ROWS": len(df),
               "QUERY_SUMMARY_STATISTICS": json.loads(df.describe().to_json(orient="records")),
                "SAMPLE_QUERY": sample_query,
                "SAMPLE_RESULT": json.loads(sample_result.to_json(orient="records")),
               }
                
        return res

    def plotly_dotplot(self, 
                       x_col: str, 
                       y_col: str, 
                       color_col: str = None, 
                       size_col: str = None, 
                       text_col: str = None, 
                       title: str = None, 
                       x_title: str = None, 
                       y_title: str = None, 
                       color_title: str = None, 
                       size_title: str = None, 
                       color_continuous_scale: str = "Viridis", 
                       query: str = "<sql query to generate data>",
                       ) -> Dict[str, Any]:
        
        """Create a dotplot using plotly express, using the results of a query to populate the data.
        
        Args:
            query (str): SQL query to run against the in-memory database.
            x_col (str): Column to use for the x axis.
            y_col (str): Column to use for the y axis.
            color_col (str, optional): Column to use for the color. Defaults to None.
            size_col (str, optional): Column to use for the size. Defaults to None.
            text_col (str, optional): Column to use for the text. Defaults to None.
            title (str, optional): Title of the plot. Defaults to None.
            x_title (str, optional): Title of the x axis. Defaults to None.
            y_title (str, optional): Title of the y axis. Defaults to None.
            color_title (str, optional): Title of the color axis. Defaults to None.
            size_title (str, optional): Title of the size axis. Defaults to None.
            color_continuous_scale (str, optional): Name of the color scale to use. Defaults to "Viridis".

        Returns:
            Dict[str, Any]: Success or failure message and summary statistics of the executed query.
        """
        query_results = self._query_db(query)
        fig = px.scatter(query_results,
                            x = x_col,
                            y = y_col,
                            color = color_col,
                            size = size_col,
                            text = text_col,
                            title = title,
                            labels = {x_col: x_title,
                                        y_col: y_title,
                                        color_col: color_title,
                                        size_col: size_title},
                            color_continuous_scale = color_continuous_scale,
                            )
        self._send_to_ui(fig)

        res = {"INFO": "The user has been show the plot, be sure to describe what they are seeing. DO NOT attempt to display the plot again.",
                "TOTAL_ROWS": len(query_results),
                "QUERY_SUMMARY_STATISTICS": json.loads(query_results.describe().to_json(orient="records")),
                }
        
        return res
    
    def plotly_barplot(self, 
                       x_col: str,
                       y_col: str,
                       nbins: int = 30,
                       group_col: str = None,
                       text_col: str = None,
                       title: str = None,
                       x_title: str = None,
                       y_title: str = None,
                       # w/ GPT-3.5 and barplot at least, putting the query after the parameters helped align the two better than putting it first
                       query: str = "<sql query to generate data>",
                       ) -> Dict[str, Any]:
        """Create a barplot or histogram using plotly express, using the results of a query to populate the data.
        
        Args:
            x_col (str): Column to use for the x axis. If continuous, the nbins argument can be used to bin the data.
            y_col (str): Column to use for the y axis.
            nbins (int, optional): Number of bins to use for the x axis. Defaults to 30.
            group_col (str, optional): Column to use for grouping, indicated by color. Defaults to None.
            text_col (str, optional): Column to use for the text labels. Defaults to None.
            title (str, optional): Title of the plot. Defaults to None.
            x_title (str, optional): Title of the x axis. Defaults to None.
            y_title (str, optional): Title of the y axis. Defaults to None.
            query (str): SQL query to run against the in-memory database. Use GROUP BY and COUNT as necessary.

        Returns:
            Dict[str, Any]: Success or failure message and summary statistics of the executed query.
        """

        query_results = self._query_db(query)
        ## check to see if the x-axis column is continuous or discrete
        if query_results[x_col].dtype == "int64" or query_results[x_col].dtype == "float64":
            fig = px.histogram(query_results,
                                x = x_col,
                                y = y_col,
                                color = group_col,
                                title = title,
                                labels = {x_col: x_title,
                                            y_col: y_title,
                                            group_col: "Group",
                                            text_col: "Text"},
                                nbins = nbins,
                                )
        else:
            fig = px.bar(query_results,
                            x = x_col,
                            y = y_col,
                            color = group_col,
                            title = title,
                            labels = {x_col: x_title,
                                        y_col: y_title,
                                        group_col: "Group",
                                        text_col: "Text"},
                            )

        self._send_to_ui(fig)

        res = {"INFO": "The user has been show the plot, be sure to describe what they are seeing. DO NOT attempt to display the plot again.",
                "TOTAL_ROWS": len(query_results),
                "QUERY_SUMMARY_STATISTICS": json.loads(query_results.describe().to_json(orient="records")),
                }
        
        return res
                       

    

    ## given a table and a column, summarizes the column contents.
    ## does so by first computing a one-dimensional umap of the embeddings
    ## and recursively splitting the data into two clusters until the
    ## message size of the data to be summarized is less than 8k tokens
    def recursive_summarize(self, table_name: str, column_name: str, embedding_column_name: str = "embedding", max_tokens: int = 8000) -> str:
        """Summarize a column of data from a table using a recursive clustering approach.
        
        Args:
            table_name (str): Name of the table to query.
            column_name (str): Name of the column to summarize.
            embedding_column_name (str, optional): Name of the column containing the embeddings. Defaults to "embedding".
            max_tokens (int, optional): Maximum number of tokens to allow in the context window. Defaults to 8000.
            
        Returns:
            str: Summary of the column contents."""

        ## get the embeddings for the column
        query = f"SELECT {column_name}, {embedding_column_name} FROM {table_name} WHERE {column_name} IS NOT NULL"
        df = self._query_db(query)
        embeddings = np.array([json.loads(embedding) for embedding in df[embedding_column_name].tolist()])
        # ## reduce the embeddings to 1 dimension
        # reducer = umap.UMAP(n_components=1)
        # embeddings = reducer.fit_transform(embeddings)

        util_agent = UtilityAgent("Summarizer", 
                                      system_message=textwrap.dedent("""You are a literature summarizer. 
                                                                     You will be given a set of texts, your goal is to produce a title and two summaries: a very short summary, and a longer summary. The short summary should be 3-5 sentences, and the longer summary should be 2-3 paragraphs. The title should be less than 10 words, but very specific to the summaries produced. The blocks may themselves consist of such summaries."""
                                                                    ).strip(),
                                      model = "gpt-3.5-turbo-16k-0613")
        
        texts = df[column_name].tolist()

        ## recursively cluster the embeddings until the message size is less than max_tokens
        def recursive_cluster(texts, embeddings, max_tokens):
            text_blocks = "\n\n".join(texts)
            message = f"Please summarize the following texts, producing a title, a short summary, and a longer summary:\n\n{text_blocks}"
            
            # base-case, we can fit all of the text in the context window
            if(util_agent.compute_token_cost(message) < max_tokens):
                summary = list(util_agent.chat(message))[-1]
                return {'summary': summary, 'texts': texts}
            
           
            ## recursive case, we need to split the data into two clusters
            clusterer = AgglomerativeClustering(n_clusters=2, metric = "cosine", linkage = "average")
            clusters = clusterer.fit_predict(embeddings)

            ## split the text blocks and embeddings based on labels in clusters.labels_
            cluster_0_texts = [text for text, label in zip(texts, clusters) if label == 0]
            cluster_0_embeddings = [embedding for embedding, label in zip(embeddings, clusters) if label == 0]
            cluster_1_texts = [text for text, label in zip(texts, clusters) if label == 1]
            cluster_1_embeddings = [embedding for embedding, label in zip(embeddings, clusters) if label == 1]

            ## recursively summarize each cluster
            cluster_0_summary = recursive_cluster(cluster_0_texts, cluster_0_embeddings, max_tokens)
            cluster_1_summary = recursive_cluster(cluster_1_texts, cluster_1_embeddings, max_tokens)

            text_blocks = cluster_0_summary['summary'] + "\n\n" + cluster_1_summary['summary']

            message = f"Please summarize the following texts, producing a title, a short summary, and a longer summary:\n\n{text_blocks}"
            summary = list(util_agent.chat(message))[-1]

            res = {'summary': summary, 'texts': [cluster_0_texts, cluster_1_texts]}

            pp.pprint(res)
            self._send_to_ui(res)
            return res

        return recursive_cluster(texts, embeddings, max_tokens)


    
    def sql_query_table(self, query: str, table_name: str, if_exists: str = "replace") -> Dict[str, Any]:
        """Save a table to the in-memory database from an SQL query.
        
        Args:
            query (str): SQL query to run against the in-memory database.
            table_name (str): Name of the table to save the results to.
            if_exists (str, optional): "replace" or "append". Defaults to "replace", "append" can be used to add to an existing table, for example to save the most recent search results to a running table.
            
        Returns:
            Dict[str, Any]: Success or failure message and summary statistics of the executed query."""
        query_results = self._query_db(query)
        query_results.to_sql(table_name, self.db, if_exists=if_exists)


        res = {"INFO": "Table saved.",
               "TOTAL_ROWS": len(query_results),
               "QUERY_SUMMARY_STATISTICS": json.loads(query_results.describe().to_json(orient="records")),
               }
        
        return res


    def search(self, query: str, limit = 100) -> Dict[str, Any]:
        """Search for a query string in the Semantic Scholar database.
        
        Args:
            query (str): Query string to search for.
            
        Returns:
            Dict[str, Any]: Success or failure message, and sample of the top results.
        """
        print("Searching for: " + query)
        results = self.sch.search_paper(query, 
                                        limit = limit,
                                        fields = ['title', 
                                                  'paperId',
                                                  'url', 
                                                  'year', 
                                                  'authors',
                                                  'venue', 
                                                  'abstract', 
                                                  'fieldsOfStudy',
                                                  'openAccessPdf',
                                                  'citationCount', 
                                                  'influentialCitationCount',
                                                  'embedding',
                                                  'tldr'])


        reslist = []
        for paper_obj in results.items:
            tldr = paper_obj["tldr"]
            if tldr is not None:
                tldr = tldr["text"]
            else:
                tldr = ""

            embedding = paper_obj["embedding"]
            if embedding is not None:
                embedding = embedding["vector"]
            else:
                embedding = []

            openAccessPdf = paper_obj["openAccessPdf"]
            if openAccessPdf is not None:
                openAccessPdf = openAccessPdf["url"]
                url = openAccessPdf
            else:
                openAccessPdf = ""
                url = paper_obj["url"]

            ## keep top 6 authors and replace the rest with "et al."
            authors = paper_obj["authors"]
            author_names = [author["name"] for author in authors]
            if len(author_names) > 6:
                author_names = author_names[:6]
                author_names.append("et al.")
            authors = ", ".join(author_names)

            
            paper_data = {
                "paperId": paper_obj['paperId'],
                "url": url,
                "title": paper_obj['title'],
                "authors": authors,
                "year": paper_obj['year'],
                "venue": paper_obj['venue'],
                "abstract": paper_obj['abstract'],
                "openAccessPdf": openAccessPdf,
                "tldr": tldr,
                "citationCount": paper_obj['citationCount'],
                "influentialCitationCount": paper_obj['influentialCitationCount'], 
                "embedding": json.dumps(embedding),
            }
            reslist.append(paper_data)

        df = pd.DataFrame(reslist)
        self._save_df_to_db(df, "search_results")
        df.to_sql("search_results", self.db, if_exists="replace")

        df_colnames = df.columns.tolist()

        user_sample = self._query_db("SELECT title, venue, year, abstract, authors, citationCount, influentialCitationCount, tldr FROM search_results ORDER BY influentialCitationCount DESC")
        self._send_to_ui("<h4>Search Results</h4>")
        self._send_to_ui(user_sample)

        # get a sample of 5 papers ordered by influentialCitationCount
        # we just want the title, year, venue, abstract, tldr, citationCount, influentialCitationCount
        query = "SELECT title, url, authors, venue, year, tldr, citationCount, influentialCitationCount FROM search_results ORDER BY citationCount DESC LIMIT 5"
        res_df = self._query_db(query)

        res = {"INFO": "The user has been show the full results as a browsable table; here is a sample of the top papers ordered by citationCount Please format them in a compact manner, for example: '[<title>](<url>), <authors>, <venue>, <year>. Summary: <tldr>, Citations: <citationCount> (influential: <influentialCitationCount>).' \n\nFinally, summarize any common themes or notable exceptions in 3-5 sentences.",
               "COLUMNS": df_colnames,
               "TOTAL_ROWS": len(df),
               "SAMPLE_QUERY": query,
               "SAMPLE_RESULT": json.loads(res_df.to_json(orient="records")),
               }
        return res



    ##########
    ## DB Functions
    ##########

    ## given a pandas dataframe, save it to the in-memory database
    ## if the table already existss, overwrite it
    def _save_df_to_db(self, df, table_name):
        df.to_sql(table_name, self.db, if_exists="append")


    ## query the in-memory database, returning results as a pandas dataframe
    def _query_db(self, query):
        return pd.read_sql_query(query, self.db)
    


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

