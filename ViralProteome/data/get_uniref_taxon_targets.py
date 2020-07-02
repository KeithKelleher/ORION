import os
import argparse
from ViralProteome.src.loadUniRef2 import UniRefSimLoader
from Common.utils import LoggingUtil, GetData


if __name__ == '__main__':
    # create a command line parser
    ap = argparse.ArgumentParser(description='Index UniRef data files for faster parsing.')

    # command line should be like: python get_uniref_taxon_targets.py -d /projects/stars/VP_data/UniRef_data -f uniref50,uniref90,uniref100
    ap.add_argument('-d', '--data_dir', required=True, help='The location of the UniRef data files')
    ap.add_argument('-f', '--UniRef_files', required=True, help='Name(s) of input UniRef files (comma delimited)')

    # parse the arguments
    args = vars(ap.parse_args())

    # load the utility class to get the virus taxa id list
    gd = GetData()

    # uniref_data_dir: str = 'D:/Work/Robokop/VP_data/UniRef_data'
    # uniref_data_dir = '/projects/stars/VP_data/UniRef_data'
    # uniref_data_dir = '/d/Work/Robokop/VP_data/UniRef_data'
    uniref_data_dir = args['data_dir']

    # the files to process
    # in_file_list: list = ['UniRef50']  # , 'UniRef100' UniRef90 UniRef50
    in_file_list: list = args['UniRef_files'].split(',')

    LoggingUtil().print_debug_msg('Getting taxon id list')

    # get the list of target taxa
    target_taxa_set: set = gd.get_ncbi_taxon_id_set(uniref_data_dir, UniRefSimLoader().TYPE_VIRUS)

    LoggingUtil().print_debug_msg('Creating taxon search file')

    # the path to the file that contains the list of taxa to search for
    search_file_path = os.path.join(uniref_data_dir, 'taxon_list.txt')

    # write out the list of taxa to search for
    with open(search_file_path, 'w') as wfp:
        for item in target_taxa_set:
            wfp.write(f'<property type="common taxon ID" value="{item}"\n')

    LoggingUtil().print_debug_msg('Executing dos2unix command')

    # optional: execute the dos2unix command on the target taxon file to get the line endings correct
    os.system(f'dos2unix "{search_file_path}"')

    # for each uniref file type
    for file in in_file_list:
        LoggingUtil().print_debug_msg(f'Working input file: {file}')

        # get the path to the file with taxon indexes
        index_file_path = os.path.join(uniref_data_dir, f'{file.lower()}_taxon_file_indexes.txt')

        # get the in and out file paths
        uniref_infile_path: str = os.path.join(uniref_data_dir, f'{file.lower()}.xml')

        LoggingUtil().print_debug_msg(f'Executing grep command: grep -F -b -f "{search_file_path}" "{uniref_infile_path}" >> "{index_file_path}"')

        # execute the grep command using the target taxon list
        # Note: you must use the latest version of grep for this to work
        os.system(f'grep -F -b -f "{search_file_path}" "{uniref_infile_path}" >> "{index_file_path}"')
