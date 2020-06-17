"""
Cobalt's class hierarchy mimics that of the Akoma Ntoso standard. There is a single root class for
all Akoma Ntoso documents. There are subclasses for each of the Akoma Ntoso document structure types,
such as hierarchicalStructure, debateStructure, etc. Finally, there is a class for each Akoma Ntoso
document type (act, bill, judgment, etc.) that extends the corresponding structure type.
"""
from collections import OrderedDict
import re
from datetime import date

from lxml import etree, objectify
from lxml.builder import ElementMaker
from iso8601 import parse_date

from .uri import FrbrUri


ENCODING_RE = re.compile(r'encoding="[\w-]+"')

DATE_FORMAT = "%Y-%m-%d"

AKN_NAMESPACES = {
    '2.0': 'http://www.akomantoso.org/2.0',
    '3.0': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0',
}
DEFAULT_VERSION = '3.0'


def datestring(value):
    if value is None:
        return ""
    elif isinstance(value, str):
        return value
    else:
        return "%04d-%02d-%02d" % (value.year, value.month, value.day)


# Create a new objectify parser that doesn't remove blank text nodes
objectify_parser = etree.XMLParser()
objectify_parser.set_element_class_lookup(objectify.ObjectifyElementClassLookup())


class AkomaNtosoDocument:
    """ Base class for Akoma Ntoso documents.
    """
    _parser = objectify_parser

    def __init__(self, xml=None):
        # TODO: we can do this better
        encoding = ENCODING_RE.search(xml, 0, 200)
        if encoding:
            # lxml doesn't like unicode strings with an encoding element, so
            # change to bytes
            xml = xml.encode('utf-8')

        self.root = self.parse(xml)
        self.namespace = self.get_namespace()

        self.maker = objectify.ElementMaker(annotate=False, namespace=self.namespace, nsmap=self.root.nsmap)
        # the "source" attribute used on some elements where it is required.
        # contains: name, id, url
        self.source = ["cobalt", "cobalt", "https://github.com/laws-africa/cobalt"]

    def parse(self, xml, document_type=None):
        """ Parse XML and ensure it's Akoma Ntoso. Raises ValueError on error. Returns the root element.
        """
        root = objectify.fromstring(xml, parser=self._parser)

        # ensure the root element is correct
        name = root.tag.split('}', 1)[1]
        if name != 'akomaNtoso':
            raise ValueError(f"XML root element must be akomaNtoso, but got {name} instead")

        return root

    def to_xml(self, *args, encoding='utf-8', **kwargs):
        return etree.tostring(self.root, *args, encoding=encoding, **kwargs)

    def get_namespace(self):
        akn_namespaces = [ns[1] for ns in sorted(list(AKN_NAMESPACES.items()), reverse=True)]
        namespaces = list(self.root.nsmap.values())
        for ns in akn_namespaces:
            if ns in namespaces:
                return ns

        raise ValueError(f"Expected to find one of the following Akoma Ntoso XML namespaces: {', '.join(akn_namespaces)}. Only these namespaces were found: {', '.join(namespaces)}")

    def ensure_element(self, name, after, at=None):
        """ Helper to get an element if it exists, or create it if it doesn't.

        :param name: dotted path from `self` or `at`
        :param after: element after which to place the new element if it doesn't exist
        :param at: element at which to start looking, (defaults to self if None)
        """
        node = self.get_element(name, root=at)
        if node is None:
            # TODO: what if nodes in the path don't exist?
            node = self.make_element(name.split('.')[-1])
            after.addnext(node)

        return node

    def get_element(self, name, root=None):
        """ Lookup a dotted-path element, start at root (or self if root is None). Returns None if the element doesn't exist.
        """
        parts = name.split('.')
        # this avoids an lxml warning about testing against None
        if root is not None:
            node = root
        else:
            node = self

        for p in parts:
            try:
                node = getattr(node, p)
            except AttributeError:
                return None
        return node

    def make_element(self, elem):
        return getattr(self.maker, elem)()


class StructuredDocument(AkomaNtosoDocument):
    """ Common base class for AKN documents with a known document structure.
    """

    structure_type = None
    """ The name of this document's structural type.
    """

    main_content_tag = None
    """ The name of the structural type's main content element.
    """

    document_type = None
    """ The name of the document type, corresponding to the primary document XML element.
    """

    @classmethod
    def for_document_type(cls, document_type):
        """ Return the subclass for this document type.
        """
        def check_subclasses(klass):
            for k in klass.__subclasses__():
                if k.document_type and k.document_type.lower() == document_type:
                    return k
                # recurse
                x = check_subclasses(k)
                if x:
                    return x

        document_type = document_type.lower()
        return check_subclasses(cls)

    @classmethod
    def empty_document(cls, version=DEFAULT_VERSION):
        """ Return XML for an empty document of this type, using the given AKN version.
        """
        today = datestring(date.today())
        frbr_uri = FrbrUri(
            country='za',
            locality=None,
            doctype=cls.document_type,
            subtype=None,
            date=today,
            number='1',
            work_component='main',
            language='eng',
            actor=None,
            prefix=('' if version == '2.0' else 'akn'),
        )

        E = ElementMaker(nsmap={None: AKN_NAMESPACES[version]})
        content = cls.empty_document_content(E)
        attrs = cls.empty_document_attrs()

        doc = E.akomaNtoso(
            E(cls.document_type,
                E.meta(
                    E.identification(
                        E.FRBRWork(
                            E.FRBRthis(value=frbr_uri.work_uri()),
                            E.FRBRuri(value=frbr_uri.work_uri(work_component=False)),
                            E.FRBRalias(value="Untitled", name="title"),
                            E.FRBRdate(date=today, name="Generation"),
                            E.FRBRauthor(href=""),
                            E.FRBRcountry(value=frbr_uri.place),
                            E.FRBRnumber(value=frbr_uri.number),
                        ),
                        E.FRBRExpression(
                            E.FRBRthis(value=frbr_uri.expression_uri()),
                            E.FRBRuri(value=frbr_uri.expression_uri(work_component=False)),
                            E.FRBRdate(date=today, name="Generation"),
                            E.FRBRauthor(href=""),
                            E.FRBRlanguage(language=frbr_uri.language),
                        ),
                        E.FRBRManifestation(
                            E.FRBRthis(value=frbr_uri.manifestation_uri()),
                            E.FRBRuri(value=frbr_uri.manifestation_uri(work_component=False)),
                            E.FRBRdate(date=today, name="Generation"),
                            E.FRBRauthor(href=""),
                        ),
                        source="#cobalt"
                    ),
                    E.references(
                        E.TLCOrganization(eId="cobalt", href="https://github.com/laws-africa/cobalt", showAs="cobalt"),
                        source="#cobalt"
                    )
                ),
                content,
                **attrs)
        )
        return etree.tostring(doc, encoding='unicode')

    @classmethod
    def empty_document_content(cls, E):
        return E(cls.main_content_tag)

    @classmethod
    def empty_document_attrs(cls):
        return {'name': cls.document_type.lower()}

    def __init__(self, xml=None):
        """ Setup a new instance with the string in `xml`, or an empty document if the XML is not given.
        """
        if not xml:
            # use an empty document
            xml = self.empty_document()
        super().__init__(xml)

        # make, eg. ".act" an alias for ".main"
        setattr(self, self.document_type, self.main)

        # make, eg. ".body" an alias for ".main_content"
        setattr(self, self.main_content_tag, self.main_content)

    def parse(self, xml, document_type=None):
        """ Parse XML and ensure it's Akoma Ntoso.
        Raises ValueError on error. Returns the root element.
        """
        root = super().parse(xml, document_type)

        if root.countchildren() < 1:
            raise ValueError("XML root element must have at least one child")

        name = root.getchildren()[0].tag.split('}', 1)[1]
        if name != self.document_type:
            raise ValueError(f"Expected {self.document_type} as first child of root element, but got {name} instead")

        return root

    @property
    def main(self):
        """ Get the root document element.
        """
        return getattr(self.root, self.document_type)

    @property
    def main_content(self):
        """ Get the main content element of the document.
        """
        return getattr(self.main, self.main_content_tag)

    @property
    def meta(self):
        """ Get the meta element of the document.
        """
        return self.main.meta

    @property
    def title(self):
        """ Short title """
        # look for the FRBRalias element with name="title", falling back to any alias
        title = None
        for alias in self.meta.identification.FRBRWork.iterchildren(f'{{{self.namespace}}}FRBRalias'):
            if alias.get('name') == 'title':
                return alias.get('value')
            title = alias.get('value')
        return title

    @title.setter
    def title(self, value):
        # set the title on an alias attribute with name="title"
        aliases = self.meta.identification.FRBRWork.xpath('a:FRBRalias[@name="title"]', namespaces={'a': self.namespace})
        if not aliases:
            alias = self.ensure_element('meta.identification.FRBRWork.FRBRalias', self.meta.identification.FRBRWork.FRBRuri)
            alias.set('name', 'title')
            aliases = [alias]
        aliases[0].set('value', value)

    @property
    def work_date(self):
        """ Date from the FRBRWork element """
        return parse_date(self.meta.identification.FRBRWork.FRBRdate.get('date')).date()

    @work_date.setter
    def work_date(self, value):
        self.meta.identification.FRBRWork.FRBRdate.set('date', datestring(value))

    @property
    def expression_date(self):
        """ Date from the FRBRExpression element """
        return parse_date(self.meta.identification.FRBRExpression.FRBRdate.get('date')).date()

    @expression_date.setter
    def expression_date(self, value):
        self.meta.identification.FRBRExpression.FRBRdate.set('date', datestring(value))
        # update the URI
        self.frbr_uri = self.frbr_uri

    @property
    def manifestation_date(self):
        """ Date from the FRBRManifestation element """
        return parse_date(self.meta.identification.FRBRManifestation.FRBRdate.get('date')).date()

    @manifestation_date.setter
    def manifestation_date(self, value):
        self.meta.identification.FRBRManifestation.FRBRdate.set('date', datestring(value))

    @property
    def language(self):
        """ The 3-letter ISO-639-2 language code of this document """
        return self.meta.identification.FRBRExpression.FRBRlanguage.get('language', 'eng')

    @language.setter
    def language(self, value):
        self.meta.identification.FRBRExpression.FRBRlanguage.set('language', value)
        # update the URI
        self.frbr_uri = self.frbr_uri

    @property
    def frbr_uri(self):
        """ The FRBR Manifestation URI as a :class:`FrbrUri` instance that uniquely identifies this document universally. """
        uri = self.meta.identification.FRBRManifestation.FRBRuri.get('value')
        if uri:
            return FrbrUri.parse(uri)

    @frbr_uri.setter
    def frbr_uri(self, uri):
        if not isinstance(uri, FrbrUri):
            uri = FrbrUri.parse(uri)

        uri.language = self.meta.identification.FRBRExpression.FRBRlanguage.get('language', 'eng')
        uri.expression_date = '@' + datestring(self.expression_date)

        if uri.work_component is None:
            uri.work_component = 'main'

        # set URIs of the main document and components
        for component, element in self.components().items():
            uri.work_component = component
            ident = element.find(f'.//{{{self.namespace}}}meta/{{{self.namespace}}}identification')

            ident.FRBRWork.FRBRuri.set('value', uri.uri())
            ident.FRBRWork.FRBRthis.set('value', uri.work_uri())
            ident.FRBRWork.FRBRcountry.set('value', uri.place)
            self.ensure_element('FRBRnumber', at=ident.FRBRWork, after=ident.FRBRWork.FRBRcountry).set('value', uri.number)

            if uri.subtype:
                self.ensure_element('FRBRsubtype', at=ident.FRBRWork, after=ident.FRBRWork.FRBRcountry).set('value', uri.subtype)
            else:
                try:
                    # remove existing subtype
                    ident.FRBRWork.remove(ident.FRBRWork.FRBRsubtype)
                except AttributeError:
                    pass

            ident.FRBRExpression.FRBRuri.set('value', uri.expression_uri(False))
            ident.FRBRExpression.FRBRthis.set('value', uri.expression_uri())

            ident.FRBRManifestation.FRBRuri.set('value', uri.expression_uri(False))
            ident.FRBRManifestation.FRBRthis.set('value', uri.expression_uri())

    def expression_frbr_uri(self):
        """ The FRBR Expression URI as a :class:`FrbrUri` instance that uniquely identifies this document universally. """
        uri = self.meta.identification.FRBRExpression.FRBRuri.get('value')
        if uri:
            return FrbrUri.parse(uri)
        else:
            return FrbrUri.empty()

    def components(self):
        """ Get an `OrderedDict` of component name to :class:`lxml.objectify.ObjectifiedElement`
        objects. Components are this document, and `<component>` and `<attachment>` elements inside this document.
        """
        components = OrderedDict()
        frbr_uri = FrbrUri.parse(self.meta.identification.FRBRWork.FRBRthis.get('value'))
        components[frbr_uri.work_component] = self.main

        xpath = './a:attachments/a:attachment/a:*/a:meta | ./a:components/a:component/a:*/a:meta'
        for meta in self.main.xpath(xpath, namespaces={'a': self.namespace}):
            frbr_uri = FrbrUri.parse(meta.identification.FRBRWork.FRBRthis.get('value'))
            name = frbr_uri.work_component
            components[name] = meta.getparent()

        return components

    def _ensure_lifecycle(self):
        try:
            after = self.meta.publication
        except AttributeError:
            after = self.meta.identification
        node = self.ensure_element('meta.lifecycle', after=after)

        if not node.get('source'):
            node.set('source', '#' + self.source[1])
            self._ensure_reference('TLCOrganization', self.source[0], self.source[1], self.source[2])

        return node

    def _ensure_reference(self, elem, name, id, href):
        references = self.ensure_element('meta.references', after=self._ensure_lifecycle())

        ref = references.find(f'./{{{self.namespace}}}{elem}[@eId="{id}"]')
        if ref is None:
            ref = self.make_element(elem)
            ref.set('eId', id)
            ref.set('href', href)
            ref.set('showAs', name)
            references.insert(0, ref)
        return ref
