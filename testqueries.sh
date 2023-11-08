#!/usr/bin/env bash

# nodes columns: 
# id|category|name|xref|provided_by|synonym|full_name|in_taxon|in_taxon_label|symbol|description

# edges colums:
# id|original_subject|predicate|original_object|category|aggregator_knowledge_source|primary_knowledge_source|provided_by|publications|qualifiers|frequency_qualifier|has_evidence|negated|onset_qualifier|sex_qualifier|stage_qualifier|relation|subject|object



# ## echo "Counts of triple types: subject category, predicate, object category"
# duckdb monarch.duckdb <<EOF
# .headers on
# .mode column
# WITH
#   edges_with_categories AS (
#     SELECT
#       edges.*,
#       nodes1.category AS subject_category,
#       nodes2.category AS object_category
#     FROM edges
#     JOIN nodes AS nodes1 ON edges.subject = nodes1.id
#     JOIN nodes AS nodes2 ON edges.object = nodes2.id
#   ),

#   triple_type_counts AS (
#     SELECT
#       count(*) AS count,
#       subject_category,
#       predicate,
#       object_category
#     FROM edges_with_categories
#     GROUP BY subject_category, predicate, object_category
#     ORDER BY count(*) DESC
#   )
  
#   SELECT * FROM triple_type_counts;
# EOF

# example results:

# count    subject_category                         predicate                                           object_category                        
# -------  ---------------------------------------  --------------------------------------------------  ---------------------------------------
# 2760204  biolink:Gene                             biolink:interacts_with                              biolink:Gene                           
# 1489641  biolink:Gene                             biolink:expressed_in                                biolink:GrossAnatomicalStructure       
# 881987   biolink:Gene                             biolink:has_phenotype                               biolink:PhenotypicFeature              
# 838103   biolink:Gene                             biolink:enables                                     biolink:BiologicalProcessOrActivity    
# 746463   biolink:Gene                             biolink:actively_involved_in                        biolink:BiologicalProcessOrActivity    
# 550848   biolink:Gene                             biolink:orthologous_to                              biolink:Gene                           
# 498417   biolink:Gene                             biolink:located_in                                  biolink:CellularComponent              


# duckdb monarch.duckdb <<EOF
# .headers on
# .mode tabs
# WITH
#     edges_with_categories AS (
#         SELECT
#           edges.*,
#           nodes1.category AS subject_category,
#           nodes2.category AS object_category
#         FROM edges
#         JOIN nodes AS nodes1 ON edges.subject = nodes1.id
#         JOIN nodes AS nodes2 ON edges.object = nodes2.id
#     ),

#     triple_type_counts AS (
#         SELECT
#           count(*) AS count,
#           subject_category,
#           predicate,
#           object_category
#         FROM edges_with_categories
#         GROUP BY subject_category, predicate, object_category
#         ORDER BY count(*) DESC
#     ),

#     -- now we need to get the first 3 examples of each triple type
#     -- we can do this by joining the edges table to the triple_type_counts table
#     -- and then using the row_number() window function to get the first 3 rows
#     -- for each triple type

#     edges_with_row_numbers AS (
#         SELECT
#             triple_type_counts.count as tpc,
#             edges_with_categories.subject_category as sub_cat,
#             edges_with_categories.subject,
#             edges_with_categories.predicate,
#             edges_with_categories.object_category as obj_cat,
#             edges_with_categories.object,
#             row_number() OVER (PARTITION BY edges_with_categories.subject_category, edges_with_categories.subject_category, edges_with_categories.subject_category) AS row_number
#         FROM edges_with_categories
#         JOIN triple_type_counts ON
#             edges_with_categories.subject_category = triple_type_counts.subject_category AND
#             edges_with_categories.predicate = triple_type_counts.predicate AND
#             edges_with_categories.object_category = triple_type_counts.object_category
#         ),

#     three_per_triple_type AS (
#         SELECT * FROM edges_with_row_numbers WHERE row_number <= 3
#         ),

#     with_names_and_descriptions AS (
#         SELECT
#             three_per_triple_type.tpc,
#             three_per_triple_type.sub_cat,
#             nodes1.name AS subject_name,
#             nodes1.description AS subject_description,
#             three_per_triple_type.predicate,
#             three_per_triple_type.obj_cat,
#             nodes2.name AS object_name,
#             nodes2.description AS object_description
#         FROM three_per_triple_type
#         JOIN nodes AS nodes1 ON three_per_triple_type.subject = nodes1.id
#         JOIN nodes AS nodes2 ON three_per_triple_type.object = nodes2.id
#     )

#     SELECT * FROM with_names_and_descriptions;
# EOF



duckdb monarch.duckdb <<EOF
.headers on
.mode column
WITH RECURSIVE
    descendants AS (
        SELECT
            edges.subject AS descendant,
            edges.object AS ancestor,
            1 AS path_length
        FROM edges
        WHERE edges.predicate = 'biolink:subclass_of' AND
            edges.object = 'MONDO:0020066'
        UNION ALL
        SELECT
            edges.subject AS descendant,
            edges.object AS ancestor,
            path_length + 1 AS path_length
        FROM edges
        JOIN descendants ON edges.object = descendants.descendant
        WHERE edges.predicate = 'biolink:subclass_of'
    ),

    -- now lets enrich those with the names of the nodes
    descendants_with_names AS (
        SELECT
            descendants.descendant,
            descendants.ancestor,
            descendants.path_length,
            nodes1.name AS descendant_name,
            nodes2.name AS ancestor_name
        FROM descendants
        JOIN nodes AS nodes1 ON descendants.descendant = nodes1.id
        JOIN nodes AS nodes2 ON descendants.ancestor = nodes2.id
    )

    select * from descendants_with_names;

EOF
