# Copyright (c) 2014 VMware, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import httplib

import mock
import requests
import suds

from oslo.vmware import exceptions
from oslo.vmware import service
from oslo.vmware import vim_util
from tests import base


class ServiceMessagePluginTest(base.TestCase):
    """Test class for ServiceMessagePlugin."""

    def test_add_attribute_for_value(self):
        node = mock.Mock()
        node.name = 'value'
        plugin = service.ServiceMessagePlugin()
        plugin.add_attribute_for_value(node)
        node.set.assert_called_once_with('xsi:type', 'xsd:string')

    def test_marshalled(self):
        plugin = service.ServiceMessagePlugin()
        context = mock.Mock()
        plugin.marshalled(context)
        context.envelope.prune.assert_called_once_with()
        context.envelope.walk.assert_called_once_with(
            plugin.add_attribute_for_value)


class ServiceTest(base.TestCase):

    def setUp(self):
        super(ServiceTest, self).setUp()
        patcher = mock.patch('suds.client.Client')
        self.addCleanup(patcher.stop)
        self.SudsClientMock = patcher.start()

    def test_retrieve_properties_ex_fault_checker_with_empty_response(self):
        try:
            service.Service._retrieve_properties_ex_fault_checker(None)
            assert False
        except exceptions.VimFaultException as ex:
            self.assertEqual([exceptions.NOT_AUTHENTICATED],
                             ex.fault_list)

    def test_retrieve_properties_ex_fault_checker(self):
        fault_list = ['FileFault', 'VimFault']
        missing_set = []
        for fault in fault_list:
            missing_elem = mock.Mock()
            missing_elem.fault.fault.__class__.__name__ = fault
            missing_set.append(missing_elem)
        obj_cont = mock.Mock()
        obj_cont.missingSet = missing_set
        response = mock.Mock()
        response.objects = [obj_cont]

        try:
            service.Service._retrieve_properties_ex_fault_checker(response)
            assert False
        except exceptions.VimFaultException as ex:
            self.assertEqual(fault_list, ex.fault_list)

    def test_request_handler(self):
        managed_object = 'VirtualMachine'
        resp = mock.Mock()

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            return resp

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        ret = svc_obj.powerOn(managed_object)
        self.assertEqual(resp, ret)

    def test_request_handler_with_retrieve_properties_ex_fault(self):
        managed_object = 'Datacenter'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            return None

        svc_obj = service.Service()
        attr_name = 'retrievePropertiesEx'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimFaultException,
                          svc_obj.retrievePropertiesEx,
                          managed_object)

    def test_request_handler_with_web_fault(self):
        managed_object = 'VirtualMachine'
        fault_list = ['Fault']

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            fault_string = mock.Mock()
            fault_string.getText.return_value = "MyFault"

            fault_children = mock.Mock()
            fault_children.name = "name"
            fault_children.getText.return_value = "value"
            child = mock.Mock()
            child.get.return_value = fault_list[0]
            child.getChildren.return_value = [fault_children]
            detail = mock.Mock()
            detail.getChildren.return_value = [child]
            doc = mock.Mock()
            doc.childAtPath = mock.Mock(side_effect=[fault_string, detail])
            raise suds.WebFault(None, doc)

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)

        try:
            svc_obj.powerOn(managed_object)
        except exceptions.VimFaultException as ex:
            self.assertEqual(fault_list, ex.fault_list)
            self.assertEqual({'name': 'value'}, ex.details)
            self.assertEqual("MyFault", ex.msg)

    def test_request_handler_with_attribute_error(self):
        managed_object = 'VirtualMachine'
        svc_obj = service.Service()
        # no powerOn method in Service
        service_mock = mock.Mock(spec=service.Service)
        svc_obj.client.service = service_mock
        self.assertRaises(exceptions.VimAttributeException,
                          svc_obj.powerOn,
                          managed_object)

    def test_request_handler_with_http_cannot_send_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            raise httplib.CannotSendRequest()

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimSessionOverLoadException,
                          svc_obj.powerOn,
                          managed_object)

    def test_request_handler_with_http_response_not_ready_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            raise httplib.ResponseNotReady()

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimSessionOverLoadException,
                          svc_obj.powerOn,
                          managed_object)

    def test_request_handler_with_http_cannot_send_header_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            raise httplib.CannotSendHeader()

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimSessionOverLoadException,
                          svc_obj.powerOn,
                          managed_object)

    def test_request_handler_with_connection_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            raise requests.ConnectionError()

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimConnectionException,
                          svc_obj.powerOn,
                          managed_object)

    def test_request_handler_with_http_error(self):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            raise requests.HTTPError()

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exceptions.VimConnectionException,
                          svc_obj.powerOn,
                          managed_object)

    @mock.patch.object(vim_util, 'get_moref', return_value=None)
    def test_request_handler_no_value(self, mock_moref):
        managed_object = 'VirtualMachine'
        svc_obj = service.Service()
        ret = svc_obj.UnregisterVM(managed_object)
        self.assertIsNone(ret)

    def _test_request_handler_with_exception(self, message, exception):
        managed_object = 'VirtualMachine'

        def side_effect(mo, **kwargs):
            self.assertEqual(managed_object, mo._type)
            self.assertEqual(managed_object, mo.value)
            raise Exception(message)

        svc_obj = service.Service()
        attr_name = 'powerOn'
        service_mock = svc_obj.client.service
        setattr(service_mock, attr_name, side_effect)
        self.assertRaises(exception, svc_obj.powerOn, managed_object)

    def test_request_handler_with_address_in_use_error(self):
        self._test_request_handler_with_exception(
            service.ADDRESS_IN_USE_ERROR,
            exceptions.VimSessionOverLoadException)

    def test_request_handler_with_conn_abort_error(self):
        self._test_request_handler_with_exception(
            service.CONN_ABORT_ERROR, exceptions.VimSessionOverLoadException)

    def test_request_handler_with_resp_not_xml_error(self):
        self._test_request_handler_with_exception(
            service.RESP_NOT_XML_ERROR, exceptions.VimSessionOverLoadException)

    def test_request_handler_with_generic_error(self):
        self._test_request_handler_with_exception(
            'GENERIC_ERROR', exceptions.VimException)

    def test_get_session_cookie(self):
        svc_obj = service.Service()
        cookie_value = 'xyz'
        cookie = mock.Mock()
        cookie.name = 'vmware_soap_session'
        cookie.value = cookie_value
        svc_obj.client.options.transport.cookiejar = [cookie]
        self.assertEqual(cookie_value, svc_obj.get_http_cookie())

    def test_get_session_cookie_with_no_cookie(self):
        svc_obj = service.Service()
        cookie = mock.Mock()
        cookie.name = 'cookie'
        cookie.value = 'xyz'
        svc_obj.client.options.transport.cookiejar = [cookie]
        self.assertIsNone(svc_obj.get_http_cookie())


class MemoryCacheTest(base.TestCase):
    """Test class for MemoryCache."""

    def test_get_set(self):
        cache = service.MemoryCache()
        cache.put('key1', 'value1')
        cache.put('key2', 'value2')
        self.assertEqual('value1', cache.get('key1'))
        self.assertEqual('value2', cache.get('key2'))
        self.assertEqual(None, cache.get('key3'))

    @mock.patch('suds.reader.DocumentReader.download')
    def test_shared_cache(self, mock_reader):
        cache1 = service.Service().client.options.cache
        cache2 = service.Service().client.options.cache
        self.assertIs(cache1, cache2)

    @mock.patch('oslo.vmware.openstack.common.timeutils.utcnow_ts')
    def test_cache_timeout(self, mock_utcnow_ts):
        mock_utcnow_ts.side_effect = [100, 125, 150, 175, 195, 200, 225]

        cache = service.MemoryCache()
        cache.put('key1', 'value1', 10)
        cache.put('key2', 'value2', 75)
        cache.put('key3', 'value3', 100)

        self.assertIsNone(cache.get('key1'))
        self.assertEqual('value2', cache.get('key2'))
        self.assertIsNone(cache.get('key2'))
        self.assertEqual('value3', cache.get('key3'))
