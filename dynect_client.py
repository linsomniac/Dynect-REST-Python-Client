import simplejson, urllib2, urllib, sys

class LoginFailed(Exception):
  '''Exception raised when a login fails.  Includes these attributes:

    - status : The status returned by the server.
    - msgs : A list of dictionaries with information about the failure,
        which include the keys "INFO", "SOURCE", "ERR_CD", and "LVL" (level).

    If the login failed with an HTTP error, `msgs` will an empty list, and
    `status` will be 'HTTP Error'.
    '''
  def __init__(self, status, msgs):
    self.status = status
    self.msgs = msgs


class DynectDNSClient:
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


  def getRecords(self, hostName, type="A", domainName=None):
    if not domainName:
      domainName = self.defaultDomainName

    try:
      response = self._request('ANYRecord/%s/%s/' % (domainName, hostName), None)
      return response['data']
    except urllib2.HTTPError, e:
      if e.code == 404:
        return None
      else:
        raise e

  def addRecord(self, data, hostName, type="A", TTL=3600, domainName=None):
    url, fieldName = self._api_details(type)

    if not domainName:
      domainName = self.defaultDomainName

    url = "%s/%s/%s/" % (url, domainName, hostName)
    data = {"ttl": str(TTL),
            "rdata": { fieldName: data }}

    response = self._request(url, data)
    if response['status'] != 'success':
      return False

    response = self._publish(domainName)
    return True

  def deleteRecord(self, data, hostName, type="A", domainName=None):
    if not domainName:
      domainName = self.defaultDomainName

    data = self.getRecords(hostName, type, domainName)
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

  def _api_details(self, type):
    if type == "A":
      return ("ARecord", "address")
    else:
      return ("CNameRecord", "cname")


  def _publish(self, domainName=None):
    self._request("Zone/%s" % domainName, {"publish": True}, type="PUT")


  def _login(self):
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

  def _request(self, url, post, type=None):
    self._log('_request(url="%s", post="%s", type="%s")' % ( url, post, type ))
    fullurl = "https://api2.dynect.net/REST/%s" % url

    if not self.sessionToken and url != 'Session/':
      self._log('Doing login...')
      self._login()

    if post:
      postdata = simplejson.dumps(post)
      req = MethodRequest(fullurl, postdata)
    else:
      req = MethodRequest(fullurl)

    req.add_header('Content-Type', 'application/json')
    req.add_header('Auth-Token', self.sessionToken)
    if type:
      setattr(req, "method", type)

    resp = urllib2.urlopen(req)
    if type:
      return resp
    else:
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
