from .akn import StructuredDocument


class CollectionStructure(StructuredDocument):
    structure_type = "collectionStructure"
    main_content_tag = "collectionBody"


class Collection(CollectionStructure):
    document_type = "collection"
