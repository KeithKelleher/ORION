import os
import subprocess
import logging
import json
import argparse

from Common.utils import LoggingUtil, GetDataPullError
from Common.loader_interface import SourceDataLoader
from Common.extractor import Extractor
from Common.prefixes import NCBIGENE, DRUGBANK, UBERON, DOID, MESH, UMLS
from Common.node_types import AGGREGATOR_KNOWLEDGE_SOURCES, ORIGINAL_KNOWLEDGE_SOURCE, PRIMARY_KNOWLEDGE_SOURCE

class HetioLoader(SourceDataLoader):

    source_id: str = 'Hetio'
    provenance_id: str = 'infores:hetio'

    def __init__(self, test_mode: bool = False):
        """
        constructor
        :param test_mode - sets the run into test mode
        """
        # call the super
        super(SourceDataLoader, self).__init__()

        # set global variables
        self.hetnet_archive_file = 'hetionet-v1.0.json.bz2'
        self.hetnet_json_file = 'hetionet-v1.0.json'
        self.hetio_retrieval_script_path = os.path.dirname(os.path.abspath(__file__))
        self.data_path: str = os.path.join(os.environ['DATA_SERVICES_STORAGE'], self.source_id)
        self.data_file: str = self.hetnet_json_file
        self.test_mode: bool = test_mode

        # the final output lists of nodes and edges
        self.final_node_list: list = []
        self.final_edge_list: list = []

        # look up table for CURIE prefixes
        self.node_type_to_curie_lookup = {
            'Gene': NCBIGENE,
            'Compound': DRUGBANK,
            'Anatomy': UBERON,
            'Disease': DOID,
            'Symptom': MESH
        }

        # create a logger
        self.logger = LoggingUtil.init_logging("Data_services.Hetio.HetioLoader", level=logging.INFO, line_format='medium', log_file_path=os.environ['DATA_SERVICES_LOGS'])

    def get_latest_source_version(self) -> str:
        return '1.0'

    def get_data(self) -> int:
        """
        Gets the Hetio data.

        Hetio has a json file but it is stored in git lfs.
        Here we use a subprocess to run a shell script that fetches it.
        """
        try:
            shell_results = subprocess.run(['/bin/sh', 'pull_hetio_data.sh', self.data_path],
                                           cwd=self.hetio_retrieval_script_path)
            shell_results.check_returncode()
        except subprocess.SubprocessError as e:
            self.logger.error(f'Hetio subprocess error - {e}')
            raise GetDataPullError(f'Hetio data pull failed - {e}')

        return True

    def parse_data(self) -> dict:
        """
        Parses the data file for graph nodes/edges and writes them to the KGX csv files.

        :return: ret_val: metadata about parsing
        """
        # saving in case we need the metadata, for now it looks like we don't
        #hetnet_metadata_file_path: str = os.path.join(self.data_path, self.data_file)
        #with open(hetnet_metadata_file_path, "r") as hetnet_meta_file:
        #    het_meta_json = json.load(hetnet_meta_file)

        extractor = Extractor()

        hetnet_file_path = os.path.join(self.data_path, self.data_file)
        with open(hetnet_file_path, "r") as hetnet_json_file:
            hetnet_json = json.load(hetnet_json_file)

            """
            # grab the relevant part of the json for nodes
            nodes_array = hetnet_json['nodes']

            # run the extractor on the nodes
            extractor.json_extract(nodes_array,
                                   # subject
                                  lambda node: get_curie_from_hetio_node(node["identifier"], node['kind']),
                                  lambda node: None,  # object
                                  lambda node: None,  # predicate
                                  # subject properties
                                  lambda node: {'name': node['name']} if 'description' not in
                                                                         node['data']
                                  else {'name': node['name'],
                                        'description': node['data']['description']},
                                  lambda node: {},  # object properties
                                  lambda node: {})  # edge properties

            # possibly helping with GC
            nodes_array = None
            """
            kind_to_abbrev_lookup = hetnet_json['kind_to_abbrev']

            # grab the relevant part of the json for edges
            edges_array = hetnet_json['edges']

            extractor.json_extract(edges_array, # subject
                                   lambda edge: get_curie_from_hetio_node(edge['source_id'][1], edge['source_id'][0]),
                                   # object
                                   lambda edge: get_curie_from_hetio_node(edge['target_id'][1], edge['target_id'][0]),
                                   # predicate
                                   lambda edge: get_predicate_from_edge(edge, kind_to_abbrev_lookup),
                                   lambda edge: {},  # subject props
                                   lambda edge: {},  # object props
                                   lambda edge: get_edge_properties(edge)) # edge props)

            # return to the caller
            self.final_node_list = extractor.nodes
            self.final_edge_list = extractor.edges

            self.logger.debug(f'Parsing data file complete.')

            # return to the caller
            return extractor.load_metadata


def get_curie_from_hetio_node(hetio_node_id, node_kind):
    if node_kind == 'Gene':
        return f'{NCBIGENE}:{hetio_node_id}'
    elif node_kind == 'Side Effect':
        return f'{UMLS}:{hetio_node_id}'
    elif node_kind == 'Compound':
        return f'{DRUGBANK}:{hetio_node_id}'
    elif node_kind == 'Symptom':
        return f'{MESH}:{hetio_node_id}'
    elif node_kind == 'Pathway':
        # TODO extract the ids from these somehow - reactome and wikipathways
        # https://github.com/dhimmel/pathways/blob/master/data/pathways.tsv
        return None
    elif node_kind == 'Pharmacologic Class':
        # TODO convert FDA / NDFRT Pharmacologic class ids to something we can handle
        # example : http: // purl.bioontology.org / ontology / NDFRT / N0000175654
        return None
    else:
        # everything else is already a curie
        return hetio_node_id


def get_hetio_abbrev(edge, kind_to_abbrev_lookup):
    source_abbrev = kind_to_abbrev_lookup[edge['source_id'][0]]
    pred_abbrev = kind_to_abbrev_lookup[edge['kind']]
    target_abbrev = kind_to_abbrev_lookup[edge['target_id'][0]]
    return f'{source_abbrev}{pred_abbrev}{target_abbrev}'


hetio_abbrev_to_curie_lookup = {
    'AuG': 'RO:0002450',  # anatomy upregulates gene
    'CuG': 'RO:0002450',  # compound upregulates gene
    'DuG': 'RO:0002450',  # drug upregulates gene
    'AdG': 'RO:0002449',  # anatomy downregulates gene
    'CdG': 'RO:0002449',  # compound downregulates gene
    'DdG': 'RO:0002449',  # drug downregulates gene
    'AeG': 'RO:0002292',  # anatomy expresses gene
    'CtD': 'RO:0002606',  # compound treats disease
    'CpD': 'RO:0003307',  # compound palliates disease (used ameloriates)
    'CcSE': 'SEMMEDDB:causes',  # compound causes side effect
    'DaG': 'hetio:ASSOCIATES_DaG',  # drug associated with gene
    'GiG': 'RO:0002435',  # gene interacts with gene
    'GrG': 'RO:0002448',  # gene regulates gene
    'CbG': 'RO:0002436',  # compound binds to gene product (used molecularly interacts with)
    'DpS': 'RO:0002200',  # disease presents symptom (has phenotype)
    'DlA': 'RO:0004026',  # disease localizes in anatomy (disease has location)
    'DrD': 'SO:similar_to',  # disease resembles disease
    'CrC': 'SO:similar_to',  # compound resembles compound
    'GcG': 'RO:0002610',    # mapping covaries to correlated with
    'GpCC': 'RO:0002007',   # mapping participant cellular component to has_part/part_of
    'GpMF': 'RO:0002007',   # mapping Molecular Function to has_part/part_of
    'GpBP': 'RO:0002007'    # mapping Biological Process to has_part/part_of
}


def get_predicate_from_edge(edge, kind_to_abbrev_lookup):
    hetio_abbrev = get_hetio_abbrev(edge, kind_to_abbrev_lookup)
    curie = hetio_abbrev_to_curie_lookup.get(hetio_abbrev, None)
    if curie:
        return curie
    else:
        generated_curie = f'{edge["kind"].upper()}_{hetio_abbrev}'
        return generated_curie


hetio_source_to_provenance_lookup = {
    'Bgee': 'infores:bgee',
    'LINCS L1000': 'infores:lincs',
    'SIDER 4.1': 'infores:sider',
    'TISSUES': 'infores:tissues-expression-db',
    'II_literature': HetioLoader.provenance_id
}


def get_edge_properties(edge):
    edge_props = {}
    edge_data = edge['data']
    if 'source' in edge_data:
        edge_sources = [edge_data['source']]
    elif 'sources' in edge_data:
        edge_sources = edge_data['sources']
    for source in edge_sources:
        provenance = hetio_source_to_provenance_lookup.get(source, None)
        if provenance:
            edge_props[ORIGINAL_KNOWLEDGE_SOURCE] = provenance
            edge_props[AGGREGATOR_KNOWLEDGE_SOURCES] = [HetioLoader.provenance_id]
            break
    if ORIGINAL_KNOWLEDGE_SOURCE not in edge_props:
        edge_props[PRIMARY_KNOWLEDGE_SOURCE] = HetioLoader.provenance_id
        edge_props['hetio_source'] = edge_sources

    return edge_props


if __name__ == '__main__':
    # create a command line parser
    ap = argparse.ArgumentParser(description='Load  data files and create KGX import files.')

    ap.add_argument('-r', '--data_dir', required=True, help='The location of the  data file')

    # parse the arguments
    args = vars(ap.parse_args())

    # this is the base directory for data files and the resultant KGX files.
    data_dir: str = args['data_dir']

    # get a reference to the processor
    ldr = HetioLoader()

    # load the data files and create KGX output
    ldr.load(data_dir, data_dir)
