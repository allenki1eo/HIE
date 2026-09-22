import numpy as np
import pytest

from hie_core.datasets import HDRPlusDataset


@pytest.fixture
def rng():
    return np.random.default_rng(1234)


@pytest.fixture(scope="session")
def hdrplus_sample():
    ds = HDRPlusDataset()
    ids = ds.list_samples()
    if not ids:
        pytest.skip("no local HDR+ bursts (run `hie data download …`)")
    return ds.load_sample(ids[0])
