"""
This module defines the `main()` coroutine for the Apify Actor, executed from the `__main__.py` file.

Feel free to modify this file to suit your specific needs.

To build Apify Actors, utilize the Apify SDK toolkit, read more at the official documentation:
https://docs.apify.com/sdk/python
"""
import gzip
import boto3

# HTTPX - library for making asynchronous HTTP requests in Python, read more at https://www.python-httpx.org/
from httpx import AsyncClient

# Apify SDK - toolkit for building Apify Actors, read more at https://docs.apify.com/sdk/python
from apify import Actor

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from string import Formatter
from _string import formatter_field_name_split # type: ignore


class MyFormatter(Formatter):
    def get_value(self, field_name, args, kwargs):
        return kwargs.get(field_name, '')

    def get_field(self, field_name, args, kwargs):
        first, rest = formatter_field_name_split(field_name) 
        obj = self.get_value(first, args, kwargs) 
        
        for is_attr, i in rest:
            if is_attr:
                obj = getattr(obj, i)
            else:
                obj = obj.get(i, '')
        return obj, first


def get_dataset_url(dataset_id, **kwargs):
    url = f'https://api.apify.com/v2/datasets/{dataset_id}/items'
    
    # Add query to the url
    if len(kwargs) > 0:
        url += f'?{urlencode(kwargs).lower()}'

    return url


def upload_to_s3(aws_access_key_id, aws_secret_access_key, bucket, key, data, gzip_compression):
    s3client = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    # Actor.log.info(s3client.list_buckets())

    if gzip_compression:
        data = gzip.compress(data)
        key += '.gz'
    
    Actor.log.info(f"upload_to_s3(): Upload to s3://{bucket}/{key}")
    s3client.put_object(Bucket=bucket, Body=data, Key=key)


async def main() -> None:
    async with Actor:
        # Get the input from previous actor
        actor_input = await Actor.get_input() or {}

        # Formatter will be use to substitube the AWS object key format
        fmt = MyFormatter()
        
        # These variables will be use for the rest of program
        dataset_id = actor_input['resource']['defaultDatasetId']
        format = actor_input['format']
        clean = actor_input['clean']
        aws_access_key_id = actor_input['aws_access_key_id']
        aws_secret_access_key = actor_input['aws_secret_access_key']
        bucket = actor_input['aws_bucket']
        key = fmt.format(actor_input['aws_object_key_format'], **actor_input)
        gzip_compression = actor_input['gzip_compression']
    
        # Get dataset from APIFY
        url = get_dataset_url(dataset_id=dataset_id, format=format, clean=clean)
        Actor.log.info(f"Get dataset from {url}")

        # Create an asynchronous HTTPX client
        # Download the dataset
        async with AsyncClient() as client:
            response = await client.get(url)
        
        # Upload dataset to S3
        upload_to_s3(aws_access_key_id, aws_secret_access_key, bucket, key, response.content, gzip_compression)

        # APIFY Output schema
        await Actor.push_data({
            "s3_path": f"s3://{bucket}/{key}{'.gz' if gzip_compression else ''}"
        })
