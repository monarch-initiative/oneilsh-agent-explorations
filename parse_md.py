import semantic_breaks

corpus = Corpus()
corpus.load_document("birds.md")

# previous document allow for ordering of documents within a corpus, much like sections are ordered children of a document, described below
corpus.load_document("marine_life.md", previous_document = "birds.md")

# we can use []-syntax to get a document by name
doc = corpus["birds.md"]

# children can be accessed by id
anatomy = doc.children["birds"].children["anatomy"]
# or by index
anatomy = doc.children["birds"].children[0]

# metadata stores other information in a node
print(anatomy.metadata["level"]) # prints 2
print(anatomy.metadata["id"]) # prints "anatomy"

# we can get a node's parent
birds = anatomy.parent

# given any node we can get its content
print(anatomy.get_content()) # returns "## Anatomy\nBird anatomy is a fascinating aspect..."
print(anatomy.get_content(include_sembreaks = True))

# and we can also do this recursively, in prefix order, to reconstruct the document
print(anatomy.get_content(recursive = True)) # returns "Bird anatomy is a fascinating aspect... as well as subsections on Feathers and Beaks recursively"

### 
### Setting metadata
###

# set an item for a node; if the item already exists and overwrite = False, it won't be set
anatomy.set_metadata("description", "A short segment on bird anatomy.", overwrite = True)

# set an item for a node and all children (also supports overwrite)
anatomy.set_metadata("author", "John Smith", recursive = True)

# or we can set anything that can be converted to json
anatomy.set_metadata("author", {"name": "John Smith", "email": "john@smith.com"})

# within a set of siblings, we can also get the next or previous sibling; this will be None if 
habitat = anatomy.next_sibling()

# within a set of siblings, we can also get the next or previous sibling; this will be None if 
anatomy = habitat.previous_sibling()

# we can create references to other nodes, possibly in other docs
habitat.set_metadata("dependencies", [anatomy])



# the document itself can also have metadata; this defaults to having an `id` of the filename and `level` of 0 if not specified
print(doc.id) # prints "birds.md"
print(doc.level) # prints 0

# we can set metadata for the doc
doc.set_metadata("title", "Birds of the World")

# recursive works here too
doc.set_metadata("author", "John Smith", recursive = True)


## if we've added or changed metadata, we should be able to write out those changed files to disk or as a string
## note that these both include the metadata
doc.write_to_file() # this should write the changes back to where they were loaded from
content = doc.write_to_string()

## and we can do the same for an entire corpus
corpus.write_to_files()
content = corpus.write_to_strings()
