# telebox.py
import sys

import os
from pathlib import Path

import requests
from tqdm import tqdm
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

import hashlib
from .config import Config


class Telebox:
    """
    The `Telebox` class represents a client to interact with the Telebox API.

    :param token: The access token required for authentication.
    :param folder_id: The ID of the folder to interact with.

    The class provides methods to connect, search, and perform various operations on the specified folder.

    Example usage:
        token = "your-access-token"
        folder_id = "your-folder-id"
        telebox = Telebox(token, folder_id)

    Methods:
        - connect: Connects to the Telebox server.
        - search: Searches for files in the specified folder.
        - folder: Retrieves information about the specified folder.

    Note:
        The class requires the Telebox library to be installed.

    """

    def __init__(self, token, folder_id):
        self.token = token
        self.folder_id = folder_id
        self.connect = Connect(Config.TELEBOX_BASE_URI, self.token)
        self.search = Search(self.connect)
        self.folder = Folder(self.connect)
        self.upload = Upload(self.connect)
        # self.upload_auth = UploadAuthorization(self.connect)
        # self.folder_details = FolderDetails(self.folder_id, self.connect)
        # self.folder_upload = FolderUploadFile(self.folder_id, self.connect)


class HttpClientService:
    """
    .. class:: HttpClientService

       The HttpClientService class provides methods to make HTTP GET and POST requests.

       :param base_url: The base URL that will be used for all requests.
       :type base_url: str

       .. method:: __init__(base_url)

          Constructs a new HttpClientService object.

          :param base_url: The base URL that will be used for all requests.
          :type base_url: str

       .. method:: get(endpoint, params=None)

          Sends an HTTP GET request to the specified endpoint.

          :param endpoint: The endpoint to send the request to.
          :type endpoint: str

          :param params: (optional) The query parameters to include in the request.
          :type params: dict

          :return: The JSON response from the server.
          :rtype: dict

          :raises requests.exceptions.HTTPError: If the request fails.

       .. method:: post(endpoint, params=None)

          Sends an HTTP POST request to the specified endpoint.

          :param endpoint: The endpoint to send the request to.
          :type endpoint: str

          :param params: (optional) The query parameters to include in the request.
          :type params: dict

          :return: The JSON response from the server.
          :rtype: dict

          :raises requests.exceptions.HTTPError: If the request fails.
    """

    def __init__(self, base_url):
        self.base_url = base_url

    def get(self, endpoint, params=None):
        response = requests.get(f"{self.base_url}{endpoint}", params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint, params=None):
        response = requests.post(f"{self.base_url}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()


class Connect:
    """
    Connect

    Class representing a connection to a remote server.

    Attributes:
        client (HttpClientService): The underlying HTTP client service.
        token (str): The authentication token.

    Methods:
        __init__(base_url, token)
            Initializes a new Connect instance.

        get_data(endpoint, params)
            Makes a GET request to the specified endpoint with the given parameters.

        post_data(endpoint, params)
            Makes a POST request to the specified endpoint with the given parameters.
    """

    def __init__(self, base_url, token):
        self.client = HttpClientService(base_url)
        self.token = token

    def get_data(self, endpoint, params):
        params["token"] = self.token
        return self.client.get(endpoint, params)

    def post_data(self, endpoint, params):
        params["token"] = self.token
        return self.client.post(endpoint, params)


class Search:
    """
     Initialize a Search object.

    Args:
        connect: The connection object used for making API calls.

    Attributes:
        connect: The connection object used for making API calls.
        url: The URL of the search file.
    """

    def __init__(self, connect):
        self.connect = connect
        self.url = Config.TELEBOX_SEARCH_FILE

    def search(self, filename, folder_id):
        return self.connect.get_data(self.url, {'pid': folder_id, 'name': filename, 'pageNo': 1, 'pageSize': 50})

    def folder_exists(self, filename, folder_id):
        lot = self.search(filename, folder_id)
        if isinstance(lot['data']['list'], list) and len(lot['data']['list']) != 0:
            return lot['data']['list'][0]['id'] if lot['data']['list'][0]['type'] == 'dir' and lot['data']['list'][0]['pid'] == int(folder_id) else False
        return False


class Upload:
    def __init__(self, connect):
        self.connect = connect

    def prepare(self, file_md5_of_pre_10m, file_size):
        return self.connect.get_data(Config.TELEBOX_UPLOAD_FASE1, {'fileMd5ofPre10m': file_md5_of_pre_10m, 'fileSize': file_size})

    @staticmethod
    def upload(url, file):
        size = os.path.getsize(file)
        with open(file, "rb") as file:
            # Send the PUT request
            response = requests.put(url, data=file)
        return response

    def finish_upload(self, file_md5_of_pre_10m, file_size, pid, name):
        return self.connect.get_data(Config.TELEBOX_UPLOAD_FASE3, {'fileMd5ofPre10m': file_md5_of_pre_10m, 'fileSize': file_size, 'pid': pid, 'diyName': name})

    def upload_file(self, file, folder_id):
        file_size = os.path.getsize(file)
        file_md5_of_pre_10m = self.get_md5_of_first_10mb(file)
        lot = self.prepare(file_md5_of_pre_10m, file_size)
        if lot['status'] == 600:
            return 1

        if lot['status'] != 1:
            sys.exit("Prepare: Execution stopped. Cannot upload files")

        url = lot['data']['signUrl']
        self.upload(url, file)
        lotf = self.finish_upload(file_md5_of_pre_10m, file_size, folder_id, os.path.basename(file))
        if lotf['status'] != 1:
            sys.exit("Finish Upload: Execution stopped. Cannot upload files")

        return lotf['data']['itemId']

    @staticmethod
    def get_md5_of_first_10mb(file_path):
        md5_hash = hashlib.md5()

        with open(file_path, 'rb') as file:
            chunk = file.read(10 * 1024 * 1024)  # read first 10MB
            if chunk:
                md5_hash.update(chunk)

        return md5_hash.hexdigest()


class Folder:
    """
     Class representing a folder.

    Args:
        connect: The connection object used to communicate with the server.

    Attributes:
        connect: The connection object used to communicate with the server.

    """

    def __init__(self, connect):
        self.connect = connect

    def create(self, filename, destination_folder_id):
        lot = self.connect.get_data(Config.TELEBOX_FOLDER_CREATE, {'pid': int(destination_folder_id),
                                                                   'name': filename,
                                                                   'isShare': 0,
                                                                   'canInvite': 1,
                                                                   'canShare': 1,
                                                                   'withBodyImg': 0,
                                                                   'desc': 'TheWNetwork Telebox Mass Creator'})
        if lot['status'] != 1:
            sys.exit("Execution stopped. Cannot create folders")

        return lot['data']['dirId']

    def get_details(self, destination_folder_id):
        return self.connect.get_data(Config.TELEBOX_FOLDER_DETAILS, {'dirId': destination_folder_id})
