"""
Either creates an n-quads files containing the content of a Manifest file or uploads the content to Fuseki.

It creates:

 1. A Named Graph for each resource using the item's IRI as the graph IRI
 2. A Named Graph for the catalogue, either using the catalogue's IRI as the graph IRI + "-catalogue" if given, or by making one up - a Blank Node
 3. All the triples in resources with roles mrr:CompleteCatalogueAndResourceLabels & mrr:IncompleteCatalogueAndResourceLabels within a Named Graph with IRI <https://background>
 4. An Olis Virtual Graph, <https://olis.dev/VirtualGraph> object using the catalogue IRI, if give, which is as an alias for all the Named Graphs from 1., 2. & 3.
 5. Multiple entries in the System Graph - Named Graph with IRI <https://olis.dev/SystemGraph> - for each Named and the Virtual Graph from 1., 2. & 3.

Run this script with the -h flag for more help, i.e. ~$ python loader.py -h
"""

import argparse
import sys
from pathlib import Path

from kurra.format import make_dataset, export_quads
from kurra.fuseki import upload
from kurra.utils import load_graph
from rdflib import DCAT, DCTERMS, PROF, RDF, SDO, SKOS
from rdflib import Graph, URIRef

try:
    from prezmanifest import MRR, OLIS, validate, __version__
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).parent.parent.resolve()))
    from prezmanifest import MRR, OLIS, validate, __version__


def load(
    manifest: Path,
    sparql_endpoint: str = None,
    destination_file: Path = None,
):
    """Loads a catalogue of data from a prezmanifest file, whose content are valid according to the Prez Manifest Model
    (https://kurrawong.github.io/prez.dev/manifest/) either into a specified quads file in the Trig format, or into a
    given SPARQL Endpoint."""

    if sparql_endpoint is not None and destination_file is not None:
        raise ValueError(
            "You may only specify either a sparql_endpoint or a export_quads_file, not both"
        )
    elif sparql_endpoint is None and destination_file is None:
        raise ValueError(
            "You must specify either a sparql_endpoint or a export_quads_file, not neither"
        )

    # load and validate prezmanifest
    g = validate(manifest)

    MANIFEST_ROOT_DIR = manifest.parent

    vg = Graph()
    vg_iri = None

    for s, o in g.subject_objects(PROF.hasResource):
        for role in g.objects(o, PROF.hasRole):
            # The catalogue - must be processed first
            if role == MRR.CatalogueData:
                for artifact in g.objects(o, PROF.hasArtifact):
                    # load the Catalogue, determine the Virtual Graph & Catalogue IRIs
                    # and fail if we can't see a Catalogue object
                    c = load_graph(MANIFEST_ROOT_DIR / str(artifact))
                    vg_iri = c.value(predicate=RDF.type, object=DCAT.Catalog)
                    if vg_iri is None:
                        raise ValueError(
                            f"ERROR: Could not create a Virtual Graph as no Catalog found in the Catalogue data"
                        )
                    catalogue_iri = URIRef(str(vg_iri) + "-catalogue")

                    # add to the System Graph
                    vg.add((vg_iri, RDF.type, OLIS.VirtualGraph))
                    vg.add((vg_iri, OLIS.isAliasFor, catalogue_iri))
                    vg_name = c.value(
                        subject=vg_iri,
                        predicate=SDO.name | DCTERMS.title | SKOS.prefLabel,
                    ) or str(vg_iri)
                    vg.add((vg_iri, SDO.name, vg_name))

                    # export the Catalogue data
                    if destination_file is not None:
                        export_quads(make_dataset(c, catalogue_iri), destination_file)
                    else:  # SPARQL
                        upload(sparql_endpoint, c, catalogue_iri)

        # non-catalogue resources
        for s, o in g.subject_objects(PROF.hasResource):
            for role in g.objects(o, PROF.hasRole):
                # The data files & background - must be processed after Catalogue
                if role in [
                    MRR.CompleteCatalogueAndResourceLabels,
                    MRR.IncompleteCatalogueAndResourceLabels,
                    MRR.ResourceData,
                ]:
                    for artifact in g.objects(o, PROF.hasArtifact):
                        if not "*" in str(artifact):
                            files = [manifest.parent / Path(str(artifact))]
                        else:
                            artifact_str = str(artifact)
                            glob_marker_location = artifact_str.find("*")
                            glob_parts = [artifact_str[:glob_marker_location], artifact_str[glob_marker_location:]]
                            files = Path(manifest.parent / Path(glob_parts[0])).glob(glob_parts[1])

                        for f in files:
                            fg = Graph().parse(f)
                            # fg.bind("rdf", RDF)

                            if role == MRR.ResourceData:
                                resource_iri = fg.value(
                                    predicate=RDF.type, object=SKOS.ConceptScheme
                                )

                            if role in [
                                MRR.CompleteCatalogueAndResourceLabels,
                                MRR.IncompleteCatalogueAndResourceLabels,
                            ]:
                                resource_iri = URIRef("http://background")

                            vg.add((vg_iri, OLIS.isAliasFor, resource_iri))
                            if destination_file is not None:
                                export_quads(
                                    make_dataset(fg, resource_iri), destination_file
                                )
                            else:  # SPARQL
                                upload(sparql_endpoint, fg, resource_iri)

        # export the System Graph
        if destination_file is not None:
            export_quads(make_dataset(vg, OLIS.SystemGraph), destination_file)
        else:  # SPARQL
            upload(sparql_endpoint, vg, OLIS.SystemGraph, append=True)

    return True


def setup_cli_parser(args=None):

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="{version}".format(version=__version__),
    )

    group.add_argument(
        "-e",
        "--endpoint",
        help="The SPARQL endpoint you want to load the data into. Cannot be specified when destination is.",
    )

    group.add_argument(
        "-d",
        "--destination",
        help="The n-quads file you want to export the data into. Cannot be specified when endpoint is.",
    )

    parser.add_argument(
        "manifest",
        help="A Manifest file to process",
        type=Path,
    )

    return parser.parse_args(args)


def cli(args=None):
    if args is None:
        args = sys.argv[1:]

    args = setup_cli_parser(args)

    load(args.manifest, args.endpoint, args.destination)


if __name__ == "__main__":
    retval = cli(sys.argv[1:])
    if retval is not None:
        sys.exit(retval)
