from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HDF_", env_file=".env", extra="ignore")

    qdrant_path: str = "data/qdrant"
    qdrant_url: str | None = None
    # Change the collection and re-ingest when changing model/chunking semantics.
    collection: str = "documents_bge_m3_256_v1"
