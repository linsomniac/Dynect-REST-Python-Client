import simplejson, urllib2, urllib, sys, httplib2

#############################
class LoginFailed(Exception):
  '''Exception raised when a login fails.  Includes these attributes:

    - status : The status returned by the server.
    - msgs : A list of dictionaries with information about the failure,
        which include the keys "INFO", "SOURCE", "ERR_CD", and "LVL" (level).

    If the login failed with an HTTP error, `msgs` will an empty list, and
    `status` will be 'HTTP Error'.
    '''
  #################################
  def __init__(self, status, msgs):
    self.status = status
    self.msgs = msgs


##############################
class HTTPResponse(Exception):
  '''Exception raised when an HTTP session results in a non-200 status.
  The attributes of this object include:

    response -- A dictionary from the HTTP call with attributes such as:
        * status
        * transfer-encoding
        * server
        * connection
        * content-type
        * date
    content -- The data read from the server in the response.
  '''
  ######################################
  def __init__(self, response, content):
    super(HTTPResponse, self).__init__()
    self.response = response
    self.content = content


###################
def joinURL(*args):
  '''Join the elements into a URI by adding "/" between the arguments, and
  removing any double slashes.
  '''
  url = '/'.join(args) + '/'

  if url.startswith('http://'):
    url = 'http://' + (url[7:].replace('//', '/'))
  elif url.startswith('https://'):
    url = 'https://' + (url[8:].replace('//', '/'))

  return url


######################
class DynectDNSClient:
  ###########################################################################
  def __init__(self, customerName, userName, password, defaultDomain = None):
    self.customerName = customerName
    self.userName = userName
    self.password = password
    self.defaultDomainName = defaultDomain
    self.sessionToken = None
    self.debugEnabled = False
    self.baseURL = 'https://api2.dynect.net/REST/'


  #############################################################
  def getCNAMERecord(self, fqdn, recordId = None, zone = None):
    if not zone: zone = self.defaultDomainName
    if not '.' in fqdn: fqdn = fqdn + '.' + zone

    resource = joinURL('CNAMERecord', zone, fqdn)
    if recordId:
      resource = joinURL(resource, recordId)

    self._request('GET', resource)


  ###############################
  def debug(self, enable = True):
    '''Enable or disable debugging messages.  If called with no arguments or
    with the argument `True`, debugging is turned on, if `False` is passed
    debugging is disabled.'''
    httplib2.debuglevel = 1 if enable else 0
    self.debugEnabled = enable


  ####################
  def _log(self, msg):
    'INTERNAL: Log a message if the debugging flag is enabled.'
    if not self.debugEnabled:
      return
    sys.stderr.write('LOG: ' + msg.rstrip() + '\n')


  #################
  def _login(self):
    self._log('_login()')
    try:
      response = self._simple_request('POST', 'Session/',
          {'customer_name': self.customerName, 'user_name': self.userName,
            'password': self.password})
    except urllib2.HTTPError, e:
      if e.code == 400:
        self._log('Login failed with HTTP 400 error, likely an account issue')
        raise LoginFailed(status = 'HTTP Error', msgs = [])
      raise

    if response['status'] != 'success':
      self._log('Login failed due to "status" of "%s"' % response['status'])
      raise LoginFailed(status = response['status'], msgs = response['msgs'])

    self.sessionToken = response['data']['token']


  #######################################################
  def _request(self, method, resource, arguments = None):
    '''Make a request to the server, if a 307 status is reported, ping
    the job periodically until it is completed.

    If an HTTP error is raised, this will simply pass it along.  This will
    perform a login if there is now existing session token.

    Arguments:
      method -- One of "GET", "POST", "DELETE", or "PUT".
      resource -- The base resource URI such as "Session/".
      arguments -- A dictionary containing the request arguments.

    Return:
      The object the server passed back.
    '''
    try:
      response = self._simple_request(method, resource, arguments)
      return response
    except HTTPResponse, e:
      if e.response['status'] != '307':
        raise

    #  get the jobid from the response
    #  periodically poll the job URL
    #  return response
    raise NotImplementedError('Need to ask dynect what I can do to trigger this for testing.')


  ##############################################################
  def _simple_request(self, method, resource, arguments = None):
    '''Make a request to the server, and return the result.

    If an HTTP error is raised, this will simply pass it along.  This will
    perform a login if there is now existing session token.

    Arguments:
      method -- One of "GET", "POST", "DELETE", or "PUT".
      resource -- The base resource URI such as "Session/".
      arguments -- A dictionary containing the request arguments.

    Return:
      The object the server passed back.
    '''
    if not self.sessionToken and resource != 'Session/':
      self._log('Doing login because _request() had no token...')
      self._login()

    self._log('_request(method=%s, resource=%s, arguments=%s)'
        % ( repr(method), repr(resource), repr(arguments), ))

    url = joinURL(self.baseURL, resource)
    http = httplib2.Http()
    body = simplejson.dumps(arguments) if arguments else None
    headers = { 'Content-Type' : 'application/json' }
    if self.sessionToken:
      headers['Auth-Token'] = self.sessionToken

    response, content = http.request(url, method = method, body = body,
        headers = headers)

    if response['status'] != '200':
      raise HTTPResponse(response, content)

    return simplejson.loads(content)


class DynectDNSClientBroken:
  '''I (Sean Reifschneider) wasn't able to get this code to work at all,
  despite a number of a fixes and various attempts.  Including this code
  most as a reference.'''

  def __init__(self, customerName, userName, password, defaultDomain=None):
    self.customerName = customerName
    self.userName = userName
    self.password = password
    self.defaultDomainName = defaultDomain
    self.sessionToken = None
    self.debugEnabled = False


  def debug(self, enable = True):
    '''Enable or disable debugging messages.  If called with no arguments or
    with the argument `True`, debugging is turned on, if `False` is passed
    debugging is disabled.'''
    self.debugEnabled = enable


  def _log(self, msg):
    'INTERNAL: Log a message if the debugging flag is enabled.'
    if not self.debugEnabled:
      return
    sys.stderr.write('LOG: ' + msg.rstrip() + '\n')


  def getRecords(self, hostName, recordType="A", domainName=None):
    self._log('getRecords(hostName="%s", recordType="%s", domainName="%s"'
        % ( hostName, recordType, domainName ))
    if not domainName:
      domainName = self.defaultDomainName

    try:
      response = self._request('ANYRecord/%s/%s/' % (domainName, hostName), None)
      return response['data']
    except urllib2.HTTPError, e:
      if e.code == 404:
        self._log('Record not found')
        return None
      else:
        raise e

  def addRecord(self, data, hostName, recordType="A", TTL=3600, domainName=None):
    self._log('addRecord(data="%s", hostName="%s", recordType="%s", '
        'TTL=%s domainName="%s"'
        % ( data, hostName, recordType, TTL, domainName ))
    url, fieldName = self._api_details(recordType)

    if not domainName:
      domainName = self.defaultDomainName

    url = "%s/%s/%s/" % (url, domainName, hostName)
    data = {"ttl": str(TTL),
            "rdata": { fieldName: data }}

    if False:
      response = self._request(url, data)
      if response['status'] != 'success':
        self._log('Lookup of record failed')
        return False

    response = self._publish(domainName)
    return True

  def deleteRecord(self, data, hostName, recordType="A", domainName=None):
    self._log('deleteRecord(data="%s", hostName="%s", recordType="%s", '
        'domainName="%s"' % ( data, hostName, recordType, domainName ))
    if not domainName:
      domainName = self.defaultDomainName

    data = self.getRecords(hostName, recordType, domainName)
    if not data:
      return False

    url = data[0]
    url = url.replace("/REST/", "")
    try:
      self._request(url, None, "DELETE")
      self._publish(domainName)
    except:
      return False

    return True

  def _api_details(self, recordType):
    if recordType == "A":
      return ("ARecord", "address")
    else:
      return ("CNAMERecord", "cname")


  def _login(self):
    self._log('_login()')
    try:
      response = self._request("Session/", {'customer_name': self.customerName,
                                                  'user_name': self.userName,
                                                  'password': self.password})
    except urllib2.HTTPError, e:
      if e.code == 400:
        self._log('Login failed with HTTP 400 error, likely an account issue')
        raise LoginFailed(status = 'HTTP Error', msgs = [])
      raise

    if response['status'] != 'success':
      self._log('Login failed due to "status" of "%s"' % response['status'])
      raise LoginFailed(status = response['status'], msgs = response['msgs'])

    self.sessionToken = response['data']['token']


  def _publish(self, domainName=None):
    self._log('Doing publish')
    self._request("Zone/%s" % domainName, {"publish": True}, method="PUT")


  def _request(self, url, post, method=None):
    if not self.sessionToken and url != 'Session/':
      self._log('Doing login because _request() had no token...')
      self._login()

    self._log('_request(url="%s", post="%s", method="%s")'
        % ( url, post, method ))
    fullurl = "https://api2.dynect.net/REST/%s" % url

    if post:
      postdata = simplejson.dumps(post)
      req = MethodRequest(fullurl, postdata)
    else:
      req = MethodRequest(fullurl)

    req.add_header('Content-Type', 'application/json')
    req.add_header('Auth-Token', self.sessionToken)
    if method:
      setattr(req, "method", method)

    try:
      resp = urllib2.urlopen(req)
    except Exception, e:
      self._log('Request raised exception: "%s"' % str(e))
      raise

    if method:
      self._log('Returning raw response')
      return resp

    data = resp.read()
    self._log('JSON Response: "%s"' % data)
    return simplejson.loads(data)


class MethodRequest(urllib2.Request):
  def __init__(self, *args, **kwargs):
    urllib2.Request.__init__(self, *args, **kwargs)
    self.method = None

  def get_method(self):
    if self.method:
      return self.method
    return urllib2.Request.get_method(self)
