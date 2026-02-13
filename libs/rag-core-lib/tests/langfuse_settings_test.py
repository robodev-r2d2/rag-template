import pytest
import os
from rag_core_lib.impl.settings.langfuse_settings import LangfuseSettings

def test_langfuse_settings_host_fix():
    # Test with the problematic host
    os.environ["LANGFUSE_HOST"] = "http://rag-langfuse-web:3000"
    os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
    os.environ["LANGFUSE_SECRET_KEY"] = "sk"
    
    settings = LangfuseSettings()
    assert settings.host == "http://rag-langfuse-web:80"

def test_langfuse_settings_host_no_change():
    # Test with a correct host
    os.environ["LANGFUSE_HOST"] = "http://other-host:3000"
    
    settings = LangfuseSettings()
    assert settings.host == "http://other-host:3000"
