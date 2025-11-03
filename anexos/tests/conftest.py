import os
import pytest
from pytest_factoryboy import register
from django.test import Client

@pytest.fixture
def client():
    return Client()