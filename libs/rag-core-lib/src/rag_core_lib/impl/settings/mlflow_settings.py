"""Contains settings for MLflow integration."""

from pydantic import Field
from pydantic_settings import BaseSettings


class MlflowSettings(BaseSettings):
    """
    MLflow settings.

    Attributes
    ----------
    tracking_uri : str
        MLflow tracking URI.
    experiment_name : str
        MLflow experiment name to log runs under.
    api_token : str | None
        Optional MLflow token for authenticated backends.
    """

    class Config:
        """Config class for reading fields from env."""

        env_prefix = "MLFLOW_"
        case_sensitive = False

    tracking_uri: str = Field(default="http://mlflow:5000")
    experiment_name: str = Field(default="rag-template")
    api_token: str | None = Field(default=None)
