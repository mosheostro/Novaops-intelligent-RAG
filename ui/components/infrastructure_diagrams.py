"""Mermaid sources for the Infrastructure & Setup page — how the knowledge base
was prepared and is managed (create_index.py, ingest.py, subjects.py,
manage.py). Static text only: building these strings touches no backend.
Private infrastructure details (collection name, region, account) never
appear here; the collection itself was provisioned outside this repository."""
from ui.components.architecture_diagrams import styled_diagram

# Outside the repository vs. managed from it; lane-level links keep each lane's direction.
LIFECYCLE = styled_diagram("""flowchart LR
    subgraph outside["Provisioned outside this repository"]
        direction TB
        store[("Vector store collection<br/>Amazon OpenSearch Serverless")]
        models["Model access<br/>Amazon Bedrock"]
        store ~~~ models
    end
    subgraph repo["Managed from this repository"]
        direction LR
        index["Create the index<br/>create_index.py<br/>only if missing"] --> ingest["Ingest the corpus<br/>ingest.py<br/>only into an empty index"]
        ingest --> runtime(["Queried at runtime<br/>see About / Architecture"])
    end
    outside --> repo
    class store,models ext
    class index,ingest app
    class runtime client
""")

# Independent of the setup flow: manage.py only inspects or deletes the provisioned collection.
ADMINISTRATION = styled_diagram("""flowchart LR
    manage["manage.py<br/>collection administration<br/>never provisions"] -->|inspect| status["Status<br/>exists · active · chunk count"]
    manage -->|delete| confirm{"Explicit<br/>confirmation?"}
    confirm -->|confirmed| delete["Delete the collection<br/>and all its data"]
    confirm -->|anything else| cancel["Cancelled<br/>collection untouched"]
    status -.-> store[("Provisioned collection<br/>Amazon OpenSearch Serverless")]
    delete -.-> store
    class manage app
    class status,cancel muted
    class confirm,delete security
    class store ext
""")

# Two lanes: prepare the records, then embed and load them.
INGESTION = styled_diagram("""flowchart TB
    subgraph prepare["1 · Prepare"]
        direction LR
        guard{"Index exists<br/>and is empty?"} -->|no| refuse["Refuse<br/>before any model call"]
        guard -->|yes| files[("Markdown documents<br/>handbook · manager playbook")]
        files --> split["Split header from body"]
        split -->|header| meta["audience · corpus<br/>last_updated"]
        split -->|document text| tag["Subject tagging<br/>one Nova call per document<br/>cached"]
        split -->|body| chunk["Chunking<br/>250 words · 50 overlap"]
    end
    subgraph load["2 · Embed and load"]
        direction LR
        record["One record per chunk<br/>text + document metadata"] --> embed["Embedding per chunk<br/>Titan · 1024 dims"]
        embed --> bulk["Bulk load<br/>wait until searchable"]
        bulk --> kb[("Index novaops-kb")]
    end
    prepare --> load
    class guard app
    class refuse muted
    class meta app
    class tag quality
    class chunk,record,embed,bulk core
    class files,kb ext
""")

ALL = {"lifecycle": LIFECYCLE, "administration": ADMINISTRATION, "ingestion": INGESTION}
