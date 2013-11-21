"""
.. module:: python-etcd
   :synopsis: A python etcd client.

.. moduleauthor:: Jose Plana <jplana@gmail.com>


"""
import urllib3
import json
import ssl

import etcd


class Client(object):
    """
    Client for etcd, the distributed log service using raft.
    """

    _MGET = 'GET'
    _MPUT = 'PUT'
    _MDELETE = 'DELETE'
    _comparison_conditions = ['prevValue', 'prevIndex', 'prevExists']

    def __init__(
            self,
            host='127.0.0.1',
            port=4001,
            read_timeout=60,
            allow_redirect=True,
            protocol='http',
            cert=None,
            ca_cert=None,
    ):
        """
        Initialize the client.

        Args:
            host (str):  IP to connect to.

            port (int):  Port used to connect to etcd.

            read_timeout (int):  max seconds to wait for a read.

            allow_redirect (bool): allow the client to connect to other nodes.

            protocol (str):  Protocol used to connect to etcd.

            cert (mixed):   If a string, the whole ssl client certificate;
                            if a tuple, the cert and key file names.

            ca_cert (str): The ca certificate. If pressent it will enable
                           validation.

        """
        self._host = host
        self._port = port
        self._protocol = protocol
        self._base_uri = "%s://%s:%d" % (protocol, host, port)
        self.version_prefix = '/v2'

        self._read_timeout = read_timeout
        self._allow_redirect = allow_redirect

        # SSL Client certificate support

        kw = {}

        if protocol == 'https':
            # If we don't allow TLSv1, clients using older version of OpenSSL
            # (<1.0) won't be able to connect.
            kw['ssl_version'] = ssl.PROTOCOL_TLSv1

            if cert:
                if isinstance(cert, tuple):
                    # Key and cert are separate
                    kw['cert_file'] = cert[0]
                    kw['key_file'] = cert[1]
                else:
                    #combined certificate
                    kw['cert_file'] = cert

            if ca_cert:
                kw['ca_certs'] = ca_cert
                kw['cert_reqs'] = ssl.CERT_REQUIRED

        self.http = urllib3.PoolManager(num_pools=10, **kw)

    @property
    def base_uri(self):
        """URI used by the client to connect to etcd."""
        return self._base_uri

    @property
    def host(self):
        """Node to connect  etcd."""
        return self._host

    @property
    def port(self):
        """Port to connect etcd."""
        return self._port

    @property
    def protocol(self):
        """Protocol used to connect etcd."""
        return self._protocol

    @property
    def read_timeout(self):
        """Max seconds to wait for a read."""
        return self._read_timeout

    @property
    def allow_redirect(self):
        """Allow the client to connect to other nodes."""
        return self._allow_redirect

    @property
    def machines(self):
        """
        Members of the cluster.

        Returns:
            list. str with all the nodes in the cluster.

        >>> print client.machines
        ['http://127.0.0.1:4001', 'http://127.0.0.1:4002']
        """
        return [
            node.strip() for node in self.api_execute(
                self.version_prefix + '/machines',
                self._MGET).split(',')
        ]

    @property
    def leader(self):
        """
        Returns:
            str. the leader of the cluster.

        >>> print client.leader
        'http://127.0.0.1:4001'
        """
        return self.api_execute(
            self.version_prefix + '/leader',
            self._MGET)

    @property
    def key_endpoint(self):
        """
        REST key endpoint.
        """
        return self.version_prefix + '/keys'


    def __contains__(self, key):
        """
        Check if a key is available in the cluster.

        >>> print 'key' in client
        True
        """
        try:
            self.get(key)
            return True
        except KeyError:
            return False




    def write(self, key, value, ttl=None, **kwdargs)
        """
        Writes the value for a key, possibly doing atomit Compare-and-Swap

        Args:
            key (str):  Key.

            value (object):  value to set

            ttl (int):  Time in seconds of expiration (optional).

            Other parameters modifying the write method are accepted:

            prevValue (str): compare key to this value, and swap only if corresponding (optional).

            prevIndex (int): modify key only if actual modifiedIndex matches the provided one (optional).
            prevExists (bool): If false, only create key; if true, only update key.

        Returns:
            client.EtcdResult

        >>> print client.write('/key', 'newValue', ttl=60, prevExists=False).value
        'newValue'

        """
        params = {
            'value': value
        }

        if ttl:
            params['ttl'] = ttl

        for condition in self._comparison_conditions:
            if condition in kwdargs:
                params[condition] = kwdargs[condition]
                #TODO: also validate input?

        path = self.key_endpoint + key
        response = self.api_execute(path, self._MPUT, params)
        return self._result_from_response(response)


    def read(self, key, **kwdargs):
        """
        Returns the value of the key 'key'.

        Args:
            key (str):  Key.

            Recognized kwd args

            recursive (bool): If you should fetch recursively a dir

            wait (bool): If we should wait and return next time the key is changed

            waitIndex (int): The index to fetch results from.

        Returns:
            client.EtcdResult (or an array of client.EtcdResult if a
            subtree is queried)

        Raises:
            KeyValue:  If the key doesn't exists.

        >>> print client.get('/key').value
        'value'

        """
        #Here we do not check the keyword args for performance.
        response = self.api_execute(self.key_endpoint + key, self._MGET, kwdargs)
        return self._result_from_response(response)

    def delete(self, key):
        """
        Removed a key from etcd.

        Args:
            key (str):  Key.

        Returns:
            client.EtcdResult

        Raises:
            KeyValue:  If the key doesn't exists.

        >>> print client.delete('/key').key
        '/key'

        """
        response = self.api_execute(self.key_endpoint + key, self._MDELETE)
        return self._result_from_response(response)


    # Higher-level methods on top of the basic primitives

    def test_and_set(self, key, value, prev_value, ttl=None):
        """
        Atomic test & set operation.
        It will check if the value of 'key' is 'prev_value',
        if the the check is correct will change the value for 'key' to 'value'
        if the the check is false an exception will be raised.

        Args:
            key (str):  Key.
            value (object):  value to set
            prev_value (object):  previous value.
            ttl (int):  Time in seconds of expiration (optional).

        Returns:
            client.EtcdResult

        Raises:
            ValueError: When the 'prev_value' is not the current value.

        >>> print client.test_and_set('/key', 'new', 'old', ttl=60).value
        'new'

        """
        return self.write(key, value, prevValue = prev_value, ttl = ttl)

    def set(self, key, value, ttl=None):
        return self.write(key, value, ttl = ttl)


    def get(self, key):
        """
        Returns the value of the key 'key'.

        Args:
            key (str):  Key.

        Returns:
            client.EtcdResult (or an array of client.EtcdResult if a
            subtree is queried)

        Raises:
            KeyValue:  If the key doesn't exists.

        >>> print client.get('/key').value
        'value'

        """
        response = self.api_execute(self.key_endpoint + key,
                                        self._MGET, {'recursive': "true"})

        return self._result_from_response(response)

    def watch(self, key, index=None):
        """
        Blocks until a new event has been received, starting at index 'index'

        Args:
            key (str):  Key.

            index (int): Index to start from.

        Returns:
            client.EtcdResult

        Raises:
            KeyValue:  If the key doesn't exists.

        >>> print client.watch('/key').value
        'value'

        """

        params = None
        method = self._MGET
        if index:
            params = {'index': index}
            method = self._MPOST

        response = self.api_execute(
            self.watch_endpoint + key,
            method,
            params=params)
        return self._result_from_response(response)


    def ethernal_watch(self, key, index=None):
        """
        Generator that will yield changes from a key.
        Note that this method will block forever until an event is generated.

        Args:
            key (str):  Key to subcribe to.
            index (int):  Index from where the changes will be received.

        Yields:
            client.EtcdResult

        >>> for event in client.ethernal_watch('/subcription_key'):
        ...     print event.value
        ...
        value1
        value2

        """
        local_index = index
        while True:
            response = self.watch(key, local_index)
            if local_index is not None:
                local_index += 1
            yield response


    def _result_from_response(self, response):
        """ Creates an EtcdResult from json dictionary """
        try:
            res = json.loads(response)
            if isinstance(res, list):
                return [etcd.EtcdResult(**v) for v in res]
            return etcd.EtcdResult(**res)
        except:
            raise etcd.EtcdException('Unable to decode server response')

    def api_execute(self, path, method, params=None):
        """ Executes the query. """
        url = self._base_uri + path

        if (method == self._MGET) or (method == self._MDELETE):
            response = self.http.request(
                method,
                url,
                fields=params,
                redirect=self.allow_redirect)

        elif method == self._MPOST:
            response = self.http.request_encode_body(
                method,
                url,
                fields=params,
                encode_multipart=False,
                redirect=self.allow_redirect)

        if response.status == 200:
            return response.data
        else:
            #throw the appropriate exception
            EtcdError.handle(**json.loads(response.data))
