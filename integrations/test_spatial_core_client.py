import json,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from integrations.spatial_core_client import SpatialClient
SCOPE="buildopt"
class Contract(unittest.TestCase):
    def test_local_http_and_scope(self):
        token="fixture-token-".ljust(40,"x")
        state={"tenant":SCOPE,"calls":0}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                state["calls"]+=1
                if self.headers.get("Authorization")!="Bearer "+token:
                    self.send_error(401);return
                if self.path=="/v1/status":r={"project":state["tenant"]}
                elif self.path=="/v1/scenes/fixture/objects":r={"objects":[{"id":"a"}]}
                elif self.path=="/v1/scenes/fixture/relations?id=a":r={"relations":[{"target":"b"}]}
                elif self.path=="/v1/scenes/fixture/distance?a=a&b=b":r={"center_distance_m":2}
                else:self.send_error(404);return
                data=json.dumps(r).encode()
                self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(data)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            c=SpatialClient(SCOPE,token,f"http://127.0.0.1:{server.server_port}")
            self.assertEqual(c.objects("fixture")["objects"][0]["id"],"a")
            self.assertEqual(c.relations("fixture","a")["relations"][0]["target"],"b")
            self.assertEqual(c.distance("fixture","a","b")["center_distance_m"],2)
            for invalid in ("../wrong",123,["fixture"]):
                with self.assertRaises(ValueError):c.objects(invalid)
            with self.assertRaises(ValueError):SpatialClient(SCOPE,token+"\n")
            state["tenant"]="wrong";before=state["calls"]
            with self.assertRaises(PermissionError):c.objects("fixture")
            self.assertEqual(state["calls"],before+1)
        finally:server.shutdown();server.server_close();thread.join()
if __name__=="__main__":unittest.main()
