# -*- encoding: utf-8 -*-
"""Telebox Implementation module"""
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from datetime import datetime
from telebox import Telebox
from .config import Config


class TeleboxImpl:
    telebox = None

    def __init__(self, arguments):
        self.telebox = Telebox(Config.TELEBOX_API, Config.TELEBOX_BASEFOLDER)
        self.main(arguments)

    def create_folder_if_not_exists(self, foldername, folder_id):
        if not (pid := self.telebox.search.folder_exists(foldername, folder_id)):
            # Folder not exists on telebox, create folder
            pid = self.telebox.folder.create(foldername, folder_id)
        return pid

    def upload_file_and_print_status(self, i, total, directory, file, subfolder_pid):
        print(f'{i + 1}/{total} - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - Uploading file: {file}')
        self.telebox.upload.upload_file(directory + '/' + file, subfolder_pid)

    def doit(self, file_list, len_list, directory, folder_pid) -> bool:
        has_directory: bool = False
        with ThreadPoolExecutor(max_workers=int(Config.USR_LIMIT_CONCURRENT)) as executor:
            for i, file in enumerate(file_list):
                if os.path.isfile(directory + '/' + file):
                    executor.submit(
                        TeleboxImpl.upload_file_and_print_status,
                        self,
                        i,
                        len_list,
                        directory,
                        file,
                        folder_pid
                    )
                if os.path.isdir(directory + '/' + file):
                    has_directory = True
        return has_directory

    def main(self, arguments):
        logging.basicConfig(level=logging.ERROR)

        currentDir = arguments.dir
        currentName = arguments.foldername

        # Searching if the folder exists
        folder_pid = int(arguments.basefolder or Config.TELEBOX_BASEFOLDER)

        folder_data = self.telebox.search.search('', folder_pid)['data']['list']

        print('Get Main Folder PID for folder ' + arguments.foldername + ' is ' + str(folder_pid))
        if arguments.foldername != 'upload':
            self.doit(os.listdir(arguments.dir), str(len(os.listdir(arguments.dir))), arguments.dir, folder_pid)

        directories = [d for d in os.listdir(arguments.dir + '/' + arguments.foldername) if os.path.isdir(os.path.join(arguments.dir + '/' + arguments.foldername, d))]
        for directory in directories:

            # Create or get Folder IDs
            print('\n\n######################################')

            if folder_data:
                subfolder = list(filter(lambda d: d['name'] == directory, folder_data))
            else:
                subfolder = None

            if not subfolder:
                # Not created yet
                subfolder_pid = self.create_folder_if_not_exists(directory, folder_pid)
                if subfolder_pid == -1:
                    sys.exit("Execution stopped. Folder not created")
            else:
                subfolder_pid = subfolder[0]['id']

            print('Creating or getting PID for folder:  ' + currentName + '/' + directory + ' is ' + str(subfolder_pid))

            # Upload Files to Telebox
            print('Start Uploading....')
            file_list = os.listdir(currentDir + '/' + currentName + '/' + directory)
            len_list = str(len(file_list))
            ret: bool = self.doit(file_list, len_list, currentDir + '/' + currentName + '/' + directory, subfolder_pid)
            if ret:
                args2 = arguments
                args2.dir = currentDir + '/' + currentName
                args2.foldername = directory
                args2.basefolder = subfolder_pid
                self.main(args2)

            print('End Uploading....')
