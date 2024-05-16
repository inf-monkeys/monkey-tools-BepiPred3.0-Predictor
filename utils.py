import os
from urllib.parse import unquote
from loguru import logger
import requests
import boto3
import boto3
from botocore.client import Config
import os
import yaml
import csv

DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")


def convert_csv_to_json(csv_file_path):
    # Read CSV file
    with open(csv_file_path, "r") as csv_file:
        csv_reader = csv.DictReader(csv_file)
        data = [row for row in csv_reader]
    return data


def load_config(filename):
    with open(filename, "r") as file:
        config = yaml.safe_load(file)
    return config


def ensure_directory_exists(dir_path):
    """
    如果目录不存在则创建目录
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path


class OSSClient:
    def __init__(
        self,
        aws_access_key_id,
        aws_secret_access_key,
        endpoint_url,
        region_name,
        bucket_name,
        base_url,
        max_content_length=100 * 1024 * 1024,  # 10MB
    ):
        self.base_url = base_url
        self.bucket_name = bucket_name
        self.max_content_length = max_content_length
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            config=Config(s3={"addressing_style": "virtual"}),
        )

    # 检查 url 里 content length 是否过大
    def get_content_length(self, url):
        r = requests.head(url)
        content_length = r.headers["content-length"]
        return int(content_length)

    # 检查文件大小是否超过限制
    def check_file_size(self, file_url):
        if self.get_content_length(file_url) > self.max_content_length:
            return False
        return True

    def extract_filename(self, url):
        # 从URL中提取文件名部分
        filename = url.split("/")[-1]
        # 去掉可能存在的URL参数
        filename = filename.split("?")[0]
        return unquote(filename)

    def download_file(self, file_url):
        try:
            logger.info(f"Downloading file from {file_url}")
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            filename = self.extract_filename(file_url)
            ensure_directory_exists(DOWNLOAD_FOLDER)
            final_path = os.path.join(DOWNLOAD_FOLDER, filename)
            with open(final_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return final_path
        except requests.RequestException as e:
            logger.error(f"Failed to download file: {e}")
            raise Exception(f"Failed to download file: {e}")

    def upload_file(self, file_path, key):
        """上传到 TOS

        返回最终的文件地址
        """
        try:
            self.client.upload_file(file_path, self.bucket_name, key)
            return self.base_url + "/" + key
        except Exception as e:
            print("fail with unknown error: {}".format(e))

    def upload_bytes(self, key, bytes):
        self.client.put_object(Bucket=self.bucket_name, Key=key, Body=bytes)

    def __get_file_extension(self, file_path):
        _, file_extension = os.path.splitext(file_path)
        return file_extension

    def upload_directory(self, directory_path, file_extensions=None, url_prefix=None):
        return self.__upload_directory_recursive(
            os.path.dirname(directory_path), directory_path, file_extensions, url_prefix
        )

    def __upload_directory_recursive(
        self, root_folder, directory_path, file_extensions=None, url_prefix=None
    ):
        logger.info(f"Uploading directory {directory_path}")
        result_map = {}
        # 遍历目录
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)

            # 判断是文件还是目录
            if os.path.isfile(item_path):
                # 如果是文件，进行上传
                if file_extensions:
                    file_extension = self.__get_file_extension(item_path)
                    if file_extension not in file_extensions:
                        continue
                file_key = item_path.replace(root_folder, "")
                if file_key[0] == "/":
                    file_key = file_key[1:]
                if url_prefix:
                    file_key = f"{url_prefix}{file_key}"
                file_url = self.upload_file(item_path, file_key)
                logger.info(f"Uploaded file {item} to {file_url}")
                result_map[item] = file_url
            elif os.path.isdir(item_path):
                # 如果是目录，递归调用函数
                result_map[item] = self.__upload_directory_recursive(
                    root_folder, item_path, file_extensions, url_prefix
                )

        return result_map


config_data = load_config("config.yaml")
port = config_data.get("port", 5000)
s3_config = config_data.get("s3")
proxy_config = config_data.get("proxy", {})

aws_access_key_id = s3_config.get("accessKeyId")
aws_access_key_secret = s3_config.get("secretAccessKey")
endpoint_url = s3_config.get("endpoint")
region_name = s3_config.get("region")
bucket_name = s3_config.get("bucket")
base_url = s3_config.get("publicAccessUrl")

s3_client = OSSClient(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_access_key_secret,
    endpoint_url=endpoint_url,
    region_name=region_name,
    bucket_name=bucket_name,
    base_url=base_url,
)

if proxy_config.get("enabled", False):
    proxy_url = proxy_config.get("url")
    if not proxy_url:
        raise ValueError("Proxy URL is not provided")
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url

    exclude = proxy_config.get("exclude", [])
    if exclude:
        if not isinstance(exclude, list):
            raise ValueError("Exclude should be a list of strings")

    # Add localhost
    exclude.append("localhost")
    exclude.append("127.0.0.1")
