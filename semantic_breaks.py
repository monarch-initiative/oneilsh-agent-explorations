test_doc = '''
Information before the first sembreak (which should be at level 1) is ignored in parsing, but should be kept if the document metadata is updated.

<!--sembreak
{"id": "birds", "level": 1}
sembreak-->
# Birds
Birds are a diverse group of warm-blooded vertebrates constituting the class Aves. 

<!--sembreak 
{"id": "anatomy", "level": 2, "metadata": {"author": "Shawn O'Neil", "dependencies": ["./feathers", "../habitat", "definitions.md:terms/scientific/habitat"]}} 
sembreak-->
## Anatomy
Bird anatomy is a fascinating aspect ...

Note that this section has additional metadata, including an author and dependencies on other sections or documents

<!--sembreak 
{"id": "feathers", "level": 3} 
sembreak-->

### Feathers
Feathers are unique to birds and are a defining characteristic of the class Aves. 

<!--sembreak 
{"id": "beaks", "level": 3} 
sembreak-->
### Beaks
Birds' beaks are highly adapted to the type of diet they consume. 

<!--sembreak
{"id": "habitat", "level": 2}
sembreak-->

## Habitat and Distribution
Birds inhabit a variety of ecosystems, from the Arctic to the deserts.

### Migration
Many bird species undertake seasonal migrations...

<!--sembreak {"id": "conservation", "level": 2} sembreak-->

## Conservation
Conservation of birds is crucial as they play vital roles in ecosystems ...
'''



###########
#### Desired Usage
###########


# corpus = Corpus()
# corpus.load_document("birds.md")
# corpus.load_document("marine_life.md")

# ## children nodes can be accessed directly by id
# birds_doc: Node = corpus.get_node("birds.md")
# anatomy: Node = birds_doc.get_node("birds").get_node("anatomy")

# ## we can get node by absolute path from a corpus, or relative path from another node
# anatomy: Node = corpus.get_node("/birds.md/birds/anatomy")
# habitat: Node = anatomy.get_node("../habitat")

# all nodes are gauranteed to have at least an id and a level
# print(anatomy.level) # prints 2
# print(anatomy.id) # prints "anatomy"

# ## given any node we can get its content, which is everything between the sembreaks
# print(anatomy.get_content()) # returns "## Anatomy\nBird anatomy is a fascinating aspect..."

# ## we can also get back the content including the sembreaks
# print(anatomy.get_content(include_sembreaks = True))

# ## and get content recursively, which begins with the nodes content and recursively adds child content in order
# print(anatomy.get_content(recursive = True))

# ## if we get contents on a document recursively with sembreaks, it should reconstruct the document with updated sembreak metadata
# birds_doc_str = birds_doc.get_content(recursive = True, include_sembreaks = True)

# ### 
# ### Setting metadata
# ###

# # set an item for a node; if the item already exists and overwrite = False, it won't be set
# anatomy.set_metadata("description", "A short segment on bird anatomy.", overwrite = True)

# # set an item for a node and all children (also supports overwrite)
# anatomy.set_metadata("author", "John Smith", recursive = True)

# # or we can set anything that can be converted to json
# anatomy.set_metadata("author", {"name": "John Smith", "email": "john@smith.com"})


## now we need to be able to create a Corpus and specify documents to parse, based on the contained sembreak data
## 
## note that the birds.md example above should be created as part of the corpus like this:

# corpus:
#   - id: birds.md
#     level: 0
#     content: |
#       This chapter introduces birds, including their anatomy, habitat, and conservation.
#     metadata: {}
#     children:
#       - id: birds
#         level: 1
#         content: |
#             # Birds
#             Birds are a diverse group of warm-blooded vertebrates constituting the class Aves. They are characterized by feathers, beaks, the ability to fly, and lay hard-shelled eggs. Birds are found worldwide and range in size from the 5 cm bee hummingbird to the 2.75 m ostrich.
#         metadata: {}
#         children:
#           - id: anatomy
#             level: 2
#             content: |
#               ## Anatomy
#               Bird anatomy is a fascinating aspect that allows them to adapt to various environments and habits. Key features include feathers, beaks, and a lightweight skeleton, which are essential for flight in most species.
#               
#               note that this section has additional metadata, including an author and dependencies on other sections or documents
#               
#             metadata:
#               author: "Shawn O'Neil"
#               dependencies:
#                 # . refers to the current node, so this is dependent on it's own child
#                 - "./feathers"
#                 # .. refers to the parent node, so this refers to a sibling at the same level at this node
#                 - "../habitat"
#                 # we can also refer to nodes within documents, using / to represent the corpus much like an absolute path
#                 - "/definitions.md/terms/scientific/habitat"
#             children:
#               - id: feathers
#                 level: 3
#                 content: |
#                   
#                   ### Feathers
#                   Feathers are unique to birds and are a defining characteristic of the class Aves. They serve multiple functions such as providing insulation, enabling flight, and aiding in camouflage and display. The coloration of feathers can be vibrant and varies widely, serving purposes like attracting mates and providing camouflage.
#                   
#                 metadata: {}
#                 children: []
#               - id: beaks
#                 level: 3
#                 content: |
#                   ### Beaks
#                   Birds' beaks are highly adapted to the type of diet they consume. For instance, finches have stout, short beaks for eating seeds, while eagles have sharp, hooked beaks for tearing meat. The beak is a vital tool for foraging, feeding, and sometimes, self-defense.
#                   
#                 metadata: {}
#                 children: []
#           - id: habitat
#             level: 2
#             content: |
#               
#               ## Habitat and Distribution
#               Birds inhabit a variety of ecosystems, from the Arctic to the deserts. They are highly adaptable and can be found in virtually every environment on Earth. The distribution of bird species is influenced by the availability of food, water, shelter, and breeding sites.
#               
#               ### Migration
#               Many bird species undertake seasonal migrations, often covering great distances to exploit different geographic habitats. Migration is primarily triggered by the availability of food and the need for suitable breeding grounds. Birds navigate during migration using a combination of innate biological senses and environmental cues.
#               
#             metadata: {}
#             children: []
#           - id: conservation
#             level: 2
#             content: |
#               ## Conservation
#               Conservation of birds is crucial as they play vital roles in ecosystems as pollinators, seed dispersers, and predators. The decline in bird populations can be indicative of broader environmental issues. Conservation efforts include habitat preservation, legal protection, and rehabilitation of endangered species.
#             metadata: {}
#             children: []            

## When creating Corpus and parsing logic, we will need to keep in mind:
## *. The sembreak data is stored as JSON in an HTML comment
## *. The content of a node is defined as everything between its defining sembreak and the next one, exactly as is
## *. The sembreak structure may not exactly match the structure of the document, and should be the only thing relied upon
## *. The sembreak structure is defined such that nodes next to each other of the same level are siblings, using the same parent/child structure as typically defined in HTML or markdown
## *. The sembreak structure must be well-formed, with documents being at level 0 and children being at the level of their parent + 1
## *. The sembreak structure must be unique, with no two nodes having the same id with any siblings; ID duplicates can occur in other documents or sections however since they are referenced with paths




from typing import Dict, List, Any, Optional, Tuple
import json
import os
import re

# forward declarations
class Corpus:
    pass

class Node:
    pass


class Node:
    """Represents a node in a document tree, or a multi-document tree, in which case the node is a document or even a collection of documents.
    
    Args:
        content (str): Content of the node.
        parent (Node): Parent of the node.
        metadata (dict): Metadata for the node.
    """
    def __init__(self, id: str, level: int, content: str, corpus: Corpus, parent: Node = None, metadata: Dict[str, Any] = {}):
        self.corpus = corpus
        self.parent = parent

        self.id: str = id
        self.content: str = content
        self.level: int = level
        self.metadata: Dict[str, Any] = metadata
        self.children: Dict[str, Node] = {}



    def get_node(self, path: str) -> Optional[Node]:
        """Get a node by path.
        
        Args:
            path (str): Path to the node, as either relative to the current node or absolute to the corpus. Examples: "anatomy", "/birds.md/birds/anatomy", "../habitat".
            
        Returns:
            Node: Node.
        """
        parts = path.split("/")
        first_part = parts[0]

        # if this is an absolute path, we need to start at the root of the corpus
        if first_part == "/":
            return self.corpus.get_node(path[1:])
        
        if first_part == "..":
            if self.parent is None:
                raise ValueError(f"Cannot get parent .. of node with ID {self.id}")
            return self.parent.get_node("/".join(parts[1:]))

        if first_part not in self.children:
            raise KeyError(f"Document with ID '{first_part}' not found in corpus.")


        if len(parts) == 1:
            return self.children[first_part]

        rest = "/".join(parts[1:])

        return self.children[first_part].get_node(rest)



    def get_metadata(self, key: str, check_ancestors = False) -> Any:
        """Get a metadata value for this node.
        
        Args:
            key (str): Key.
            check_ancestors (bool, optional): Whether to check the node's ancestors for the key. Defaults to False.
            
        Returns:
            Any: Value.
        """
        if key in self.metadata:
            return self.metadata[key]

        if check_ancestors and self.parent is not None:
            return self.parent.get_metadata(key, check_ancestors = check_ancestors)

        return None

    # TODO: maybe we want to expand the option how to incorporate the new metadata, to either overwrite, merge, or ignore
    def set_metadata(self, key: str, value: Any, recursive: bool = False, overwrite: bool = False) -> None:
        """Set a metadata key/value pair for this node.
        
        Args:
            key (str): Key.
            value (Any): Value.
            recursive (bool, optional): Whether to set the metadata recursively for all children. Defaults to False.
            overwrite (bool, optional): Whether to overwrite an existing key. Defaults to False.
        """
        if key not in self.metadata or overwrite:
            self.metadata[key] = value

        if recursive:
            # child is of type Node
            for child in self.children.values():
                child.set_metadata(key, value, recursive = recursive, overwrite = overwrite)


    def get_content(self, recursive: bool = False, include_sembreaks: bool = False) -> str:
        """Get the content of this node, optionally including the current sembreak data, and optionally including the content of all children.
        
        Args:
            recursive (bool, optional): Whether to get the content recursively for all children. Defaults to False.
            include_sembreaks (bool, optional): Whether to include semantic breaks in the returned content. Defaults to False.
            
        Returns:
            str: Content.
        """
        my_content_build = []

        if include_sembreaks:
            my_sembreak = f"\n<!--sembreak\n{json.dumps({'id': self.id, 'level': self.level, 'metadata': self.metadata})}\nsembreak-->\n"
            my_content_build.append(my_sembreak)

        my_content_build.append(self.content)

        my_content = "".join(my_content_build)

        # base case - we aren't supposed to be recursive, or there's no children
        if not recursive or len(self.children) == 0:
            return my_content
        
        recursive_build = [my_content]
        # otherwise we are recursive, and there's children to worry about    
        for child in self.children.values():
            recursive_build.append(child.get_content(recursive = recursive, include_sembreaks = include_sembreaks))

        return "".join(recursive_build)




# Function to build the node tree
def build_node_tree(parsed_data: List[Dict[str, Any]], parent: Node) -> None:
    while parsed_data:
        first = parsed_data.pop(0)
        level = first['sembreak']['level']
        id = first['sembreak']['id']
        content = first['content']
        metadata = first['sembreak'].get('metadata', {})
        
        if level != parent.level + 1 and level != parent.level:
            raise ValueError(f"Expected node at level {parent.level + 1}, but found node '{id}' at level {level}.")
        
        node = Node(id=id, level=level, content=content, corpus=parent.corpus, parent=parent, metadata=metadata)
        parent.children[id] = node
        
        while parsed_data:
            next_level = parsed_data[0]['sembreak']['level']
            if next_level == level:
                break
            if next_level > level:
                build_node_tree(parsed_data, parent=node)
            else:
                break


def validate_structure(parsed_data: List[Dict[str, Any]]) -> None:
    """
    Validate the well-formed structure and check for duplicate IDs among siblings.
    
    Args:
        parsed_data (List[Dict[str, Any]]): Parsed sembreaks and content from the document.
    
    Raises:
        ValueError: If the document structure is not well-formed or if duplicate IDs are found among siblings.
    """
    id_set = set()  # To keep track of IDs at the same level
    last_level = 0  # To keep track of the last seen level
    for entry in parsed_data:
        level = entry['sembreak']['level']
        id = entry['sembreak']['id']
        
        # Check for well-formed structure (each child should be at the level of their parent + 1)
        if level > last_level + 1:
            raise ValueError(f"The document is not well-formed. Found a node '{id}' at level {level} immediately after a node at level {last_level}.")
        
        # Reset the ID set if we move to a higher or same level
        if level <= last_level:
            id_set.clear()
        
        # Check for duplicate IDs among siblings
        if id in id_set:
            raise ValueError(f"Duplicate ID '{id}' found at level {level}. IDs must be unique among siblings.")
        
        id_set.add(id)
        last_level = level




class Corpus:
    def __init__(self):
        self.documents: Dict[str, Node] = {}  # A mapping from document ID to the root Node of that document

    def get_node(self, path: str) -> Optional[Node]:
        parts = path.split("/")
        first_part = parts[0]

        # it is an absolute path, so we need to start at the root of the corpus
        if first_part == "":
            return self.get_node(path[1:])

        if first_part not in self.documents:
            raise KeyError(f"Document with ID '{first_part}' not found in corpus.")

        if len(parts) == 1:
            return self.documents[first_part]

        rest = "/".join(parts[1:])

        return self.documents[first_part].get_node(rest)

    def load_document_string(self, document: str, doc_id: str) -> None:
        preamble, parsed_data = parse_sembreaks_with_preamble(document)
        validate_structure(parsed_data)
        
        # Create root node for the document with the preamble as its content
        root = Node(id=doc_id, level=0, content=preamble, corpus=self, metadata={})
        build_node_tree(parsed_data, parent=root)
        
        self.documents[doc_id] = root


    def load_document_file(self, path: str) -> None:
        with open(path, "r") as f:
            document = f.read()
        
        self.load_document_string(document, os.path.basename(path))



# Update the parsing logic to include preamble
def parse_sembreaks_with_preamble(document: str) -> Tuple[str, List[Dict[str, Any]]]:
    sembreak_pattern = r"<!--sembreak\s*(?P<json>{.*?})\s*sembreak-->"
    sembreaks = [{"start": m.start(), "end": m.end(), "sembreak": json.loads(m.group("json"))} for m in re.finditer(sembreak_pattern, document)]
    
    if not sembreaks:
        raise ValueError("The document must contain at least one semantic breakpoint.")
    
    preamble = document[:sembreaks[0]['start']].strip()  # Get the preamble before the first sembreak
    parsed_data = []
    
    for i in range(len(sembreaks)):
        start = sembreaks[i]['end']
        end = sembreaks[i + 1]['start'] if i + 1 < len(sembreaks) else None
        content = document[start:end].strip()
        parsed_data.append({"sembreak": sembreaks[i]['sembreak'], "content": content})
        
    return preamble, parsed_data





corpus = Corpus()
corpus.load_document_string(test_doc, "birds.md")
# corpus.load_document_file("./marine_life.md")

## children nodes can be accessed directly by id
birds_doc: Node = corpus.get_node("birds.md")
anatomy: Node = birds_doc.get_node("birds").get_node("anatomy")

## we can get node by absolute path from a corpus, or relative path from another node
anatomy: Node = corpus.get_node("/birds.md/birds/anatomy")
habitat: Node = anatomy.get_node("../habitat")

# all nodes are gauranteed to have at least an id and a level
print(anatomy.level) # prints 2
print(anatomy.id) # prints "anatomy"

## given any node we can get its content, which is everything between the sembreaks
print(anatomy.get_content()) # returns "## Anatomy\nBird anatomy is a fascinating aspect..."

## we can also get back the content including the sembreaks
print(anatomy.get_content(include_sembreaks = True))

## and get content recursively, which begins with the nodes content and recursively adds child content in order
print(anatomy.get_content(recursive = True))

## if we get contents on a document recursively with sembreaks, it should reconstruct the document with updated sembreak metadata
birds_doc_str = birds_doc.get_content(recursive = True, include_sembreaks = True)

