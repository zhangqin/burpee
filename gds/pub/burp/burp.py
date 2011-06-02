#!/usr/bin/env python
"""
GDS Burp Suite API

* Burp and Burp Suite are trademarks of PortSwigger Ltd.
Copyright 2008 PortSwigger Ltd. All rights reserved.
See http://portswigger.net for license terms.

Copyright (c) 2009-2010 Marcin Wielgoszewski <marcinw@gdssecurity.com>
Gotham Digital Science

This file is part of GDS Burp API.

GDS Burp API is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

GDS Burp API is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with GDS Burp API.  If not, see <http://www.gnu.org/licenses/>
"""
from .utils import parse_headers, parse_parameters
from datetime import time as _time
from datetime import datetime as _datetime
from urlparse import urljoin, urlparse
import copy
import logging

LOGGER = logging.getLogger(__name__)

HTTP_X_REQUESTED_WITH = 'X-Requested-With'
HTTP_CONTENT_TYPE = 'Content-Type'
HTTP_CONTENT_LENGTH = 'Content-Length'


class Burp(object):
    """
    This is our main Burp class that contains a single request and an
    optional response.  This data was gathered from parsing our Burp
    log file, which may have been generated by any of the Burp Suite tools.
    """
    def __init__(self, data=None, index=0):
        """
        Create a new Burp request/response object from a parsed Burp log
        file.
        """
        self.index = index
        self.host = None
        self.ip_address = None
        self.burptime = None
        self.datetime = None
        self._request = {}
        self._response = {}
        self.url = None
        self.parameters = {}
        self.replayed = []

        if hasattr(data, 'items'):
            self.__process(data)

        LOGGER.debug("Burp object created: %d", self.index)

    def __process(self, data):
        """
        Process data to fill properties of Burp object.
        """
        self.host = data.get('host', None)
        self.ip_address = data.get('ip_address', None)

        self._request.update({
             'method': data['request'].get('method'),
             'path': data['request'].get('path'),
             'version': data['request'].get('version'),
             'headers': parse_headers(data['request'].get('headers', {})),
             'body': data['request'].get('body', ""),
            })

        self._response.update({
             'version': data['response'].get('version'),
             'status': int(data['response'].get('status', 0)),
             'reason': data['response'].get('reason'),
             'headers': parse_headers(data['response'].get('headers', {})),
             'body': data['response'].get('body', ""),
            })

        if 'Date' in self.response_headers:
            # NOTE: the HTTP-date should represent the best available
            # approximation of the date and time of message generation.
            # See: http://tools.ietf.org/html/rfc2616#section-14.18
            #
            # This doesn't always indicate the exact datetime the response
            # was served, i.e., cached pages might have a Date header
            # that occurrs in the past.
            req_date = self.get_response_header('Date')

            try:
                self.datetime = _datetime.strptime(req_date,
                                                   '%a, %d %b %Y %H:%M:%S %Z')
            except (ValueError, TypeError):
                LOGGER.exception("Invalid time struct %r", req_date)
                self.datetime = None

        self.burptime = data.get('time', None)

        if self.burptime:
            # Let's take Burp's recorded time and stuff that into a 
            # datetime.time object.
            try:
                r_time, am_pm = self.burptime.split()
                hour, minute, second = map(int, r_time.split(":"))
                if hour < 12 and am_pm == 'PM':
                    hour += 12
                elif hour == 12 and am_pm == 'AM':
                    hour = 0

                self.time = _time(hour, minute, second)
            except ValueError:
                LOGGER.exception("Invalid time struct %r", self.burptime)
                self.time = _time()

        self.url = urlparse(urljoin(self.host, self._request.get('path', '/')))
        self.parameters = parse_parameters(self)

        # During parsing, we may parse an extra CRLF or two.  So to account
        # for that, we'll just grab the actual content-length from the
        # HTTP header and slice the request/response body appropriately.
        if self.get_response_header(HTTP_CONTENT_LENGTH):
            content_length = int(self.get_response_header(HTTP_CONTENT_LENGTH))
            if len(self) != content_length:
                #LOGGER.debug("Response content-length differs by %d", len(self) - content_length)
                self._response['body'] = self._response['body'][:content_length]

        if self.get_request_header(HTTP_CONTENT_LENGTH):
            content_length = int(self.get_request_header(HTTP_CONTENT_LENGTH))
            if len(self.get_request_body()) != content_length and 'amf' not in \
                self.get_request_header(HTTP_CONTENT_LENGTH):
                #LOGGER.debug("Request content-length differs by %d", len(self.get_request_body()) - content_length)
                self._request['body'] = self._request['body'][:content_length]

    def __len__(self):
        """
        @return: Content-Length of response body.
        @rtype: int
        """
        return len(self.get_response_body())

    def __repr__(self):
        return "<Burp %d>" % self.index

    def get_request_body(self):
        """
        Return request body.

        @rtype: string
        """
        return self._request['body']

    def get_request_method(self):
        """
        Return request method.

        @rtype: string
        """
        return self._request['method']

    def get_request_version(self):
        """
        Return request version.

        @rtype: string
        """
        return self._request['version']

    def get_request_header(self, name, default=''):
        """
        Return request header.

        @param name: Name of the request header.
        @param default: Default value to return if header does not exist.
        @return: If header exists returns its value, else an empty string.
        @rtype: string
        """
        return self._request['headers'].get(name.title(), default)

    def get_request_headers(self):
        """
        Return request headers.

        @rtype: dict
        """
        return self._request['headers']

    def get_request_path(self):
        """
        Return request path.

        @rtype: string
        """
        return self._request['path']

    def get_response_version(self):
        """
        Return response version.

        @rtype: string
        """
        return self._response['version']

    def get_response_status(self):
        """
        Return response status.

        @rtype: string
        """
        return self._response['status']

    def get_response_reason(self):
        """
        Return response reason.

        @rtype: string
        """
        return self._response['reason']

    def get_response_header(self, name, default=''):
        """
        Return response header.

        @param name: Name of the response header.
        @param default: Default value to return if header does not exist.
        @return: If header exists return its value, else an empty string.
        @rtype: string
        """
        return self._response['headers'].get(name.title(), default)

    def get_response_headers(self):
        """
        Return response headers.

        @rtype: dict
        """
        return self._response['headers']

    def get_response_body(self):
        """
        Return response body.

        @rtype: string
        """
        return self._response['body']


    # request helper property's
    body = property(get_request_body)
    headers = property(get_request_headers)
    method = property(get_request_method)

    # response helper property's
    response = property(get_response_body)
    response_headers = property(get_response_headers)
    status = property(get_response_status)
    reason = property(get_response_reason)

    @property
    def is_xhr(self):
        """
        Returns True if the request was made via an XMLHttpRequest,
        by checking the request headers for HTTP_X_REQUESTED_WITH.
        """
        return HTTP_X_REQUESTED_WITH in self.get_request_headers()

    @property
    def is_secure(self):
        """
        Returns True if the request is secure; that is, if it was made
        with HTTPS.
        """
        return self.url.scheme == 'https'

    @property
    def is_multipart(self):
        """
        Indicates whether the request is a Multipart request according
        to RFC2388.
        """
        return self.get_request_header(HTTP_CONTENT_TYPE).startswith('multipart/')

    @property
    def is_delete(self):
        """
        Returns True if this request was made using the DELETE method.
        """
        return self.method == "DELETE"

    @property
    def is_get(self):
        """
        Returns True if this request was made using the GET method.
        """
        return self.method == "GET"

    @property
    def is_options(self):
        """
        Returns True if this request was made using the OPTIONS method.
        """
        return self.method == "OPTIONS"

    @property
    def is_post(self):
        """
        Returns True if this request was made using the POST method.
        """
        return self.method == "POST"

    @property
    def is_put(self):
        """
        Returns True if this request was made using the PUT method.
        """
        return self.method == "PUT"

    @property
    def is_trace(self):
        """
        Returns True if this request was made using the TRACE method.
        """
        return self.method == "TRACE"


class Scanner(object):
    def __init__(self):
        # Reference implementation using httplib2
        #
        #self.conn = httplib2.Http()
        pass

    def replay(self, request, url=None, method=None, body=None, headers=None):
        """
        Replay a Burp object, appending the result as a Burp object to the
        original replayed list.

        @param request: A gds.pub.burp.Burp object.
        @param url: URL to override request's original url.
        @param method: Method to override request's original request method.
        @param body: Body to override request's original request body.
        @param headers: Headers to override request's original request body.
        """
        if url is None:
            url = request.url.geturl()
        if method is None:
            method = request.get_request_method()
        if body is None:
            body = request.get_request_body()
        if headers is None:
            headers = copy.deepcopy(request.get_request_headers())

        if method == "POST" and body:
            headers.update({"Content-Length": str(len(body))})

        # Reference implementation using httplib2
        #
        #response, body = self.conn.request(request.url.geturl(),
        #                                   request.get_request_method(),
        #                                   request.get_request_body(),
        #                                   request.get_request_headers())
        #
        #burpobj = Burp({'request': {'body': body,
        #                            'method': method,
        #                            'path': path,
        #                            'version': 'HTTP/1.1'},
        #                'response': {'status': response.status,
        #                             'reason': response.reason,
        #                             'version': "HTTP/%.1f" % (float(response.version)/10)},
        #                'index': 0})
        #
        #burpobj.request['headers'] = headers
        #burpobj.response['headers'] = response
        #burpobj.response['body'] = body
        #burpobj.url = urlparse(url)
        #request.replayed.append(burpobj)
