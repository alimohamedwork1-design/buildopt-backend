"""Private loopback SDK for seven project scopes. No secrets persisted."""
import base64,json,re
from urllib.request import Request,build_opener,HTTPRedirectHandler,ProxyHandler
from urllib.parse import urlsplit,urlencode
ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}')
import os
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("Redirect denied")
PROJECTS={"buildopt"}
class SpatialClient:
    def __init__(self,project,token,base="http://127.0.0.1:8092",timeout=30):
        u=urlsplit(base)
        if project not in PROJECTS or not isinstance(token,str) or not 32<=len(token)<=512 or any(not 33<=ord(c)<=126 for c in token) or u.scheme!="http" or u.hostname not in ("127.0.0.1","localhost") or u.username or u.password or u.path not in ("","/") or u.query or u.fragment or not 1<=timeout<=120:raise ValueError("Use trusted loopback endpoint and project credentials")
        self.project=project;self._token=token;self.base=base.rstrip("/");self.timeout=timeout;self.opener=build_opener(ProxyHandler({}),NoRedirect())
    def _request(self,path,data=None,limit=4*1024**2):
        body=None if data is None else json.dumps(data).encode()
        req=Request(self.base+path,data=body,headers={"Authorization":"Bearer "+self._token,"Content-Type":"application/json"})
        with self.opener.open(req,timeout=self.timeout) as r:
            raw=r.read(limit+1)
            if len(raw)>limit:raise ValueError("Response cap")
            return raw
    def status(self):
        r=json.loads(self._request("/v1/status"))
        if r["project"]!=self.project:raise PermissionError("Token project mismatch")
        return r
    def models(self):
        self.status();return json.loads(self._request("/v1/models"))
    def objects(self,scene,label=""):
        self.status()
        if not isinstance(scene,str) or not ID.fullmatch(scene) or not isinstance(label,str) or len(label)>128:raise ValueError("Invalid scene or label")
        return json.loads(self._request("/v1/scenes/"+scene+"/objects"+("?"+urlencode({"label":label}) if label else "")))
    def relations(self,scene,object_id):
        self.status()
        if not all(isinstance(x,str) and ID.fullmatch(x) for x in (scene,object_id)):raise ValueError("Invalid IDs")
        return json.loads(self._request("/v1/scenes/"+scene+"/relations?"+urlencode({"id":object_id})))
    def distance(self,scene,a,b):
        self.status()
        if not all(isinstance(x,str) and ID.fullmatch(x) for x in (scene,a,b)):raise ValueError("Invalid IDs")
        return json.loads(self._request("/v1/scenes/"+scene+"/distance?"+urlencode({"a":a,"b":b})))
    def preview(self,scene,asset):
        self.status()
        if not all(isinstance(x,str) and ID.fullmatch(x) for x in (scene,asset)):raise ValueError("Invalid IDs")
        return self._request("/v1/scenes/"+scene+"/assets/"+asset,limit=32*1024**2)
    def infer(self,model,image):
        self.status()
        if not isinstance(model,str) or not ID.fullmatch(model) or not isinstance(image,bytes) or not 0<len(image)<=4*1024**2:raise ValueError("Invalid input")
        return json.loads(self._request("/v1/infer",{"model":model,"image_base64":base64.b64encode(image).decode()}))


def connect():
    return SpatialClient("buildopt",os.environ['SPATIAL_CORE_TOKEN'])
