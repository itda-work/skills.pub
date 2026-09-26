from __future__ import annotations

import re
from dataclasses import dataclass

OWPML_NS = (
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
    'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" '
    'xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" '
    'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
    'xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
    'xmlns:epub="http://www.idpf.org/2007/ops" '
    'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" '
    'xmlns:opf="http://www.idpf.org/2007/opf/"'
)

MIME_TYPE = "application/hwp+zip"
VERSION_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
    '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
    'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="0" buildNumber="1" '
    'os="1" xmlVersion="1.4" application="cli.hwpx" appVersion="1, 0, 0, 1"/>'
)
_XML_FORBIDDEN_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def xml_escape(value: str) -> str:
    value = _XML_FORBIDDEN_CONTROLS.sub("", value)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


@dataclass(frozen=True)
class ImageEntry:
    id: str
    href: str
    media_type: str
    data: bytes


class SpecProfile:
    def build_container_xml(self) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container" '
            'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf">'
            "<ocf:rootfiles>"
            '<ocf:rootfile full-path="Contents/content.hpf" media-type="application/hwpml-package+xml"/>'
            '<ocf:rootfile full-path="Preview/PrvText.txt" media-type="text/plain"/>'
            '<ocf:rootfile full-path="META-INF/container.rdf" media-type="application/rdf+xml"/>'
            "</ocf:rootfiles>"
            "</ocf:container>"
        ).encode()

    def build_manifest_xml(self) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
        ).encode()

    def build_content_hpf(
        self,
        images: list[ImageEntry],
        section_count: int,
        title: str,
        creator: str,
    ) -> bytes:
        title = title or "Document"
        creator = creator or "cli.hwpx"
        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
            f"<opf:package {OWPML_NS} version=\"\" unique-identifier=\"\" id=\"\">",
            "<opf:metadata>",
            f"<opf:title>{xml_escape(title)}</opf:title>",
            "<opf:language>ko</opf:language>",
            f'<opf:meta name="creator" content="{xml_escape(creator)}"/>',
            f'<opf:meta name="lastsaveby" content="{xml_escape(creator)}">{xml_escape(creator)}</opf:meta>',
            "</opf:metadata>",
            "<opf:manifest>",
            '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>',
        ]
        for i in range(section_count):
            parts.append(f'<opf:item id="section{i}" href="Contents/section{i}.xml" media-type="application/xml"/>')
        parts.append('<opf:item id="settings" href="settings.xml" media-type="application/xml"/>')
        for img in images:
            parts.append(
                f'<opf:item id="{xml_escape(img.id)}" href="{xml_escape(img.href)}" '
                f'media-type="{xml_escape(img.media_type)}" isEmbeded="1"/>'
            )
        parts.extend(["</opf:manifest>", "<opf:spine>", '<opf:itemref idref="header" linear="yes"/>'])
        for i in range(section_count):
            parts.append(f'<opf:itemref idref="section{i}"/>')
        parts.extend(["</opf:spine>", "</opf:package>"])
        return "".join(parts).encode()

    def build_settings_xml(self) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
            'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
            '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
            "</ha:HWPApplicationSetting>"
        ).encode()

    def build_container_rdf(self) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description rdf:about=""><ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" rdf:resource="Contents/header.xml"/></rdf:Description>'
            '<rdf:Description rdf:about="Contents/header.xml"><rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#HeaderFile"/></rdf:Description>'
            '<rdf:Description rdf:about=""><ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" rdf:resource="Contents/section0.xml"/></rdf:Description>'
            '<rdf:Description rdf:about="Contents/section0.xml"><rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#SectionFile"/></rdf:Description>'
            '<rdf:Description rdf:about=""><rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#Document"/></rdf:Description>'
            "</rdf:RDF>"
        ).encode()
