"""One bounded HTTP delivery pass to an explicitly configured loopback server."""
import argparse
import json
import os
import sqlite3
from urllib.parse import urlsplit

import httpx
from edge_delivery import Spool


def run_once(spool_path,server,email,password):
    target=urlsplit(server)
    if (target.scheme!='http' or target.hostname not in ('127.0.0.1','localhost','::1')
            or target.username or target.password or target.query or target.fragment or target.path not in ('','/')):
        raise ValueError('This development worker accepts only an explicit loopback HTTP origin')
    if not email or not password:raise ValueError('Supply dedicated local test account credentials through the environment')
    with httpx.Client(base_url=server.rstrip('/'),timeout=10,follow_redirects=False,trust_env=False) as client:
        login=client.post('/api/auth/login',json={'email':email,'password':password})
        login.raise_for_status();csrf=client.cookies.get('edgeops_csrf')
        if not csrf:raise ValueError('No authenticated CSRF session')
        try:
            def send(envelope):
                response=client.post('/api/acquisition/ingest',json=envelope,headers={'x-edgeops-csrf':csrf})
                try:result=response.json()
                except ValueError:result={}
                return response.status_code,result
            return Spool(spool_path).attempt(send)
        finally:
            # Keep the worker's browser-style session short lived; never log credentials.
            try:client.post('/api/auth/logout',headers={'x-edgeops-csrf':csrf})
            except httpx.HTTPError:pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spool',required=True);parser.add_argument('--server',required=True)
    args=parser.parse_args()
    try:result=run_once(args.spool,args.server,os.environ.get('EDGEOPS_DELIVERY_EMAIL'),os.environ.get('EDGEOPS_DELIVERY_PASSWORD'))
    except (ValueError,OSError,sqlite3.Error,httpx.HTTPError):parser.exit(1,'Delivery worker unavailable; verify local server, credentials and spool. No credentials were logged.\n')
    print(json.dumps(result))


if __name__=='__main__':main()
