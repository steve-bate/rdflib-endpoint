from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from rdflib import RDFS, Graph, Literal, URIRef
from rdflib_endpoint import SparqlEndpoint

from example.app.main import custom_concat
        
graph = Graph()

@pytest.fixture(autouse=True)
def clear_graph():
    # Workaround to clear graph without putting
    # graph, app and endpoint into a fixture
    # and modifying the test fixture usage.
    for triple in graph:
        graph.remove(triple)


app = SparqlEndpoint(
    graph=graph,
    functions={
        "https://w3id.org/um/sparql-functions/custom_concat": custom_concat,
    },
    enable_update=True
)

endpoint = TestClient(app)


def test_service_description():
    response = endpoint.get("/", headers={"accept": "text/turtle"})
    # print(response.text.strip())
    assert response.status_code == 200
    assert response.text.strip() == service_description

    response = endpoint.post("/", headers={"accept": "text/turtle"})
    assert response.status_code == 200
    assert response.text.strip() == service_description

    # Check for application/xml
    response = endpoint.post("/", headers={"accept": "application/xml"})
    assert response.status_code == 200


def test_custom_concat_json():
    response = endpoint.get("/", params={"query": concat_select}, headers={"accept": "application/json"})
    print(response.json())
    assert response.status_code == 200
    assert response.json()["results"]["bindings"][0]["concat"]["value"] == "Firstlast"

    response = endpoint.post("/", data="query=" + concat_select, headers={"accept": "application/json"})
    assert response.status_code == 200
    assert response.json()["results"]["bindings"][0]["concat"]["value"] == "Firstlast"


def test_select_noaccept_xml():
    response = endpoint.post("/", data="query=" + concat_select)
    assert response.status_code == 200


def test_select_csv():
    response = endpoint.post("/", data="query=" + concat_select, headers={"accept": "text/csv"})
    assert response.status_code == 200


label_patch = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE { ?subject rdfs:label "foo" }
INSERT { ?subject rdfs:label "bar" }
WHERE { ?subject rdfs:label "foo" }
"""


@pytest.mark.parametrize(
    "method,api_key,key_provided",
    [
        ("get", None, None),
        ("post", None, None),
        ("get", "key", False),
        ("post", "key", False),
        ("get", "key", True),
        ("post", "key", True),
    ],
)
def test_label_patch_post(method, api_key, key_provided, monkeypatch):
    if api_key:
        monkeypatch.setenv("RDFLIB_APIKEY", api_key)
    subject = URIRef("http://server.test/subject")
    headers = {}
    if key_provided:
        headers["Authorization"] = "Bearer key"
    graph.add((subject, RDFS.label, Literal("foo")))
    if method == "post":
        response = endpoint.post("/", data="update=" + label_patch, headers=headers)
    elif method == "get":
        response = endpoint.get(
            "/?update=", params={"update": label_patch}, headers=headers
        )
    else:
        raise Exception("unknown request method")
    if api_key is None or key_provided:
        assert response.status_code == 204
        assert (subject, RDFS.label, Literal("foo")) not in graph
        assert (subject, RDFS.label, Literal("bar")) in graph
    else:
        assert response.status_code == 403
        assert (subject, RDFS.label, Literal("foo")) in graph
        assert (subject, RDFS.label, Literal("bar")) not in graph


def test_multiple_accept_return_json():
    response = endpoint.get(
        "/",
        params={"query": concat_select},
        headers={"accept": "text/html;q=0.3, application/xml;q=0.9, application/json, */*;q=0.8"},
    )
    assert response.status_code == 200
    assert response.json()["results"]["bindings"][0]["concat"]["value"] == "Firstlast"


def test_multiple_accept_return_json2():
    response = endpoint.get(
        "/",
        params={"query": concat_select},
        headers={"accept": "text/html;q=0.3, application/json, application/xml;q=0.9, */*;q=0.8"},
    )
    assert response.status_code == 200
    assert response.json()["results"]["bindings"][0]["concat"]["value"] == "Firstlast"


def test_fail_select_turtle():
    response = endpoint.post("/", data="query=" + concat_select, headers={"accept": "text/turtle"})
    assert response.status_code == 422
    # assert response.json()['results']['bindings'][0]['concat']['value'] == "Firstlast"


def test_concat_construct_turtle():
    # expected to return turtle
    response = endpoint.post(
        "/",
        data="query=" + custom_concat_construct,
        headers={"accept": "application/json"},
    )
    assert response.status_code == 200
    # assert response.json()['results']['bindings'][0]['concat']['value'] == "Firstlast"


def test_concat_construct_xml():
    # expected to return turtle
    response = endpoint.post(
        "/",
        data="query=" + custom_concat_construct,
        headers={"accept": "application/xml"},
    )
    assert response.status_code == 200


def test_yasgui():
    # expected to return turtle
    response = endpoint.get(
        "/",
        headers={"accept": "text/html"},
    )
    assert response.status_code == 200


def test_bad_request():
    response = endpoint.get("/?query=figarofigarofigaro", headers={"accept": "application/json"})
    assert response.status_code == 400


concat_select = """PREFIX myfunctions: <https://w3id.org/um/sparql-functions/>
SELECT ?concat ?concatLength WHERE {
    BIND("First" AS ?first)
    BIND(myfunctions:custom_concat(?first, "last") AS ?concat)
}"""

custom_concat_construct = """PREFIX myfunctions: <https://w3id.org/um/sparql-functions/>
CONSTRUCT {
    <http://test> <http://concat> ?concat, ?concatLength .
} WHERE {
    BIND("First" AS ?first)
    BIND(myfunctions:custom_concat(?first, "last") AS ?concat)
}"""

service_description = """@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix ent: <http://www.w3.org/ns/entailment/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sd: <http://www.w3.org/ns/sparql-service-description#> .

<https://w3id.org/um/sparql-functions/custom_concat> a sd:Function .

<https://your-endpoint/sparql> a sd:Service ;
    rdfs:label "SPARQL endpoint for RDFLib graph" ;
    dc:description "A SPARQL endpoint to serve machine learning models, or any other logic implemented in Python. [Source code](https://github.com/vemonet/rdflib-endpoint)" ;
    sd:defaultDataset [ a sd:Dataset ;
            sd:defaultGraph [ a sd:Graph ] ] ;
    sd:defaultEntailmentRegime ent:RDFS ;
    sd:endpoint <https://your-endpoint/sparql> ;
    sd:extensionFunction <https://w3id.org/um/sparql-functions/custom_concat> ;
    sd:feature sd:DereferencesURIs ;
    sd:resultFormat <http://www.w3.org/ns/formats/SPARQL_Results_CSV>,
        <http://www.w3.org/ns/formats/SPARQL_Results_JSON> ;
    sd:supportedLanguage sd:SPARQL11Query ."""
