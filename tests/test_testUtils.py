# This file is part of pipe_base.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Unit tests for `lsst.pipe.base.tests`, a library for testing
PipelineTask subclasses.
"""

import shutil
import tempfile
import unittest

import lsst.utils.tests
import lsst.pex.config
import lsst.daf.butler
import lsst.daf.butler.tests as butlerTests

from lsst.pipe.base import Struct, PipelineTask, PipelineTaskConfig, PipelineTaskConnections, connectionTypes
from lsst.pipe.base.testUtils import runTestQuantum, makeQuantum, assertValidOutput


class VisitConnections(PipelineTaskConnections, dimensions={"instrument", "visit"}):
    a = connectionTypes.Input(
        name="VisitA",
        storageClass="StructuredData",
        multiple=False,
        dimensions={"instrument", "visit"},
    )
    b = connectionTypes.Input(
        name="VisitB",
        storageClass="StructuredData",
        multiple=False,
        dimensions={"instrument", "visit"},
    )
    outA = connectionTypes.Output(
        name="VisitOutA",
        storageClass="StructuredData",
        multiple=False,
        dimensions={"instrument", "visit"},
    )
    outB = connectionTypes.Output(
        name="VisitOutB",
        storageClass="StructuredData",
        multiple=False,
        dimensions={"instrument", "visit"},
    )


class PatchConnections(PipelineTaskConnections, dimensions={"skymap", "tract"}):
    a = connectionTypes.Input(
        name="PatchA",
        storageClass="StructuredData",
        multiple=True,
        dimensions={"skymap", "tract", "patch"},
    )
    b = connectionTypes.PrerequisiteInput(
        name="PatchB",
        storageClass="StructuredData",
        multiple=False,
        dimensions={"skymap", "tract"},
    )
    out = connectionTypes.Output(
        name="PatchOut",
        storageClass="StructuredData",
        multiple=True,
        dimensions={"skymap", "tract", "patch"},
    )

    def __init__(self, *, config=None):
        super().__init__(config=config)

        if not config.doUseB:
            self.prerequisiteInputs.remove("b")


class SkyPixConnections(PipelineTaskConnections, dimensions={"skypix"}):
    a = connectionTypes.Input(
        name="PixA",
        storageClass="StructuredData",
        dimensions={"skypix"},
    )
    out = connectionTypes.Output(
        name="PixOut",
        storageClass="StructuredData",
        dimensions={"skypix"},
    )


class VisitConfig(PipelineTaskConfig, pipelineConnections=VisitConnections):
    pass


class PatchConfig(PipelineTaskConfig, pipelineConnections=PatchConnections):
    doUseB = lsst.pex.config.Field(default=True, dtype=bool, doc="")


class SkyPixConfig(PipelineTaskConfig, pipelineConnections=SkyPixConnections):
    pass


class VisitTask(PipelineTask):
    ConfigClass = VisitConfig
    _DefaultName = "visit"

    def run(self, a, b):
        outA = butlerTests.MetricsExample(data=(a.data + b.data))
        outB = butlerTests.MetricsExample(data=(a.data * max(b.data)))
        return Struct(outA=outA, outB=outB)


class PatchTask(PipelineTask):
    ConfigClass = PatchConfig
    _DefaultName = "patch"

    def run(self, a, b=None):
        if self.config.doUseB:
            out = [butlerTests.MetricsExample(data=(oneA.data + b.data)) for oneA in a]
        else:
            out = a
        return Struct(out=out)


class SkyPixTask(PipelineTask):
    ConfigClass = SkyPixConfig
    _DefaultName = "skypix"

    def run(self, a):
        return Struct(out=a)


class PipelineTaskTestSuite(lsst.utils.tests.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Repository should be re-created for each test case, but
        # this has a prohibitive run-time cost at present
        cls.root = tempfile.mkdtemp()

        dataIds = {
            "instrument": ["notACam"],
            "physical_filter": ["k2020"],  # needed for expandUniqueId(visit)
            "visit": [101, 102],
            "skymap": ["sky"],
            "tract": [42],
            "patch": [0, 1],
        }
        cls.repo = butlerTests.makeTestRepo(cls.root, dataIds)
        butlerTests.registerMetricsExample(cls.repo)

        for typeName in {"VisitA", "VisitB", "VisitOutA", "VisitOutB"}:
            butlerTests.addDatasetType(cls.repo, typeName, {"instrument", "visit"}, "StructuredData")
        for typeName in {"PatchA", "PatchOut"}:
            butlerTests.addDatasetType(cls.repo, typeName, {"skymap", "tract", "patch"}, "StructuredData")
        butlerTests.addDatasetType(cls.repo, "PatchB", {"skymap", "tract"}, "StructuredData")
        for typeName in {"PixA", "PixOut"}:
            butlerTests.addDatasetType(cls.repo, typeName, {"htm7"}, "StructuredData")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.butler = butlerTests.makeTestCollection(self.repo)

    def _makeVisitTestData(self, dataId):
        """Create dummy datasets suitable for VisitTask.

        This method updates ``self.butler`` directly.

        Parameters
        ----------
        dataId : any data ID type
            The (shared) ID for the datasets to create.

        Returns
        -------
        datasets : `dict` [`str`, `list`]
            A dictionary keyed by dataset type. Its values are the list of
            integers used to create each dataset. The datasets stored in the
            butler are `lsst.daf.butler.tests.MetricsExample` objects with
            these lists as their ``data`` argument, but the lists are easier
            to manipulate in test code.
        """
        inA = [1, 2, 3]
        inB = [4, 0, 1]
        self.butler.put(butlerTests.MetricsExample(data=inA), "VisitA", dataId)
        self.butler.put(butlerTests.MetricsExample(data=inB), "VisitB", dataId)
        return {"VisitA": inA, "VisitB": inB, }

    def _makePatchTestData(self, dataId):
        """Create dummy datasets suitable for PatchTask.

        This method updates ``self.butler`` directly.

        Parameters
        ----------
        dataId : any data ID type
            The (shared) ID for the datasets to create. Any patch ID is
            overridden to create multiple datasets.

        Returns
        -------
        datasets : `dict` [`str`, `list` [`tuple` [data ID, `list`]]]
            A dictionary keyed by dataset type. Its values are the data ID
            of each dataset and the list of integers used to create each. The
            datasets stored in the butler are
            `lsst.daf.butler.tests.MetricsExample` objects with these lists as
            their ``data`` argument, but the lists are easier to manipulate
            in test code.
        """
        inA = [1, 2, 3]
        inB = [4, 0, 1]
        datasets = {"PatchA": [], "PatchB": []}
        for patch in {0, 1}:
            self.butler.put(butlerTests.MetricsExample(data=(inA + [patch])), "PatchA", dataId, patch=patch)
            datasets["PatchA"].append((dict(dataId, patch=patch), inA + [patch]))
        self.butler.put(butlerTests.MetricsExample(data=inB), "PatchB", dataId)
        datasets["PatchB"].append((dataId, inB))
        return datasets

    def testMakeQuantumNoSuchDatatype(self):
        config = VisitConfig()
        config.connections.a = "Visit"
        task = VisitTask(config=config)

        dataId = butlerTests.expandUniqueId(self.butler, {"visit": 102})
        self._makeVisitTestData(dataId)

        with self.assertRaises(ValueError):
            makeQuantum(task, self.butler, dataId, {key: dataId for key in {"a", "b", "outA", "outB"}})

    def testMakeQuantumInvalidDimension(self):
        config = VisitConfig()
        config.connections.a = "PatchA"
        task = VisitTask(config=config)
        dataIdV = butlerTests.expandUniqueId(self.butler, {"visit": 102})
        dataIdP = butlerTests.expandUniqueId(self.butler, {"patch": 0})

        inA = [1, 2, 3]
        inB = [4, 0, 1]
        self.butler.put(butlerTests.MetricsExample(data=inA), "VisitA", dataIdV)
        self.butler.put(butlerTests.MetricsExample(data=inA), "PatchA", dataIdP)
        self.butler.put(butlerTests.MetricsExample(data=inB), "VisitB", dataIdV)

        with self.assertRaises(ValueError):
            makeQuantum(task, self.butler, dataIdV, {
                "a": dataIdP,
                "b": dataIdV,
                "outA": dataIdV,
                "outB": dataIdV,
            })

    def testMakeQuantumMissingMultiple(self):
        task = PatchTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"tract": 42})
        self._makePatchTestData(dataId)

        with self.assertRaises(ValueError):
            makeQuantum(task, self.butler, dataId, {
                "a": dict(dataId, patch=0),
                "b": dataId,
                "out": [dict(dataId, patch=patch) for patch in {0, 1}],
            })

    def testMakeQuantumExtraMultiple(self):
        task = PatchTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"tract": 42})
        self._makePatchTestData(dataId)

        with self.assertRaises(ValueError):
            makeQuantum(task, self.butler, dataId, {
                "a": [dict(dataId, patch=patch) for patch in {0, 1}],
                "b": [dataId],
                "out": [dict(dataId, patch=patch) for patch in {0, 1}],
            })

    def testMakeQuantumMissingDataId(self):
        task = VisitTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"visit": 102})
        self._makeVisitTestData(dataId)

        with self.assertRaises(ValueError):
            makeQuantum(task, self.butler, dataId, {key: dataId for key in {"a", "outA", "outB"}})
        with self.assertRaises(ValueError):
            makeQuantum(task, self.butler, dataId, {key: dataId for key in {"a", "b", "outB"}})

    def testMakeQuantumCorruptedDataId(self):
        task = VisitTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"visit": 102})
        self._makeVisitTestData(dataId)

        with self.assertRaises(ValueError):
            # fourth argument should be a mapping keyed by component name
            makeQuantum(task, self.butler, dataId, dataId)

    def testRunTestQuantumVisitWithRun(self):
        task = VisitTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"visit": 102})
        data = self._makeVisitTestData(dataId)

        quantum = makeQuantum(task, self.butler, dataId,
                              {key: dataId for key in {"a", "b", "outA", "outB"}})
        runTestQuantum(task, self.butler, quantum, mockRun=False)

        # Can we use runTestQuantum to verify that task.run got called with
        # correct inputs/outputs?
        self.assertTrue(self.butler.datasetExists("VisitOutA", dataId))
        self.assertEqual(self.butler.get("VisitOutA", dataId),
                         butlerTests.MetricsExample(data=(data["VisitA"] + data["VisitB"])))
        self.assertTrue(self.butler.datasetExists("VisitOutB", dataId))
        self.assertEqual(self.butler.get("VisitOutB", dataId),
                         butlerTests.MetricsExample(data=(data["VisitA"] * max(data["VisitB"]))))

    def testRunTestQuantumPatchWithRun(self):
        task = PatchTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"tract": 42})
        data = self._makePatchTestData(dataId)

        quantum = makeQuantum(task, self.butler, dataId, {
            "a": [dataset[0] for dataset in data["PatchA"]],
            "b": dataId,
            "out": [dataset[0] for dataset in data["PatchA"]],
        })
        runTestQuantum(task, self.butler, quantum, mockRun=False)

        # Can we use runTestQuantum to verify that task.run got called with
        # correct inputs/outputs?
        inB = data["PatchB"][0][1]
        for dataset in data["PatchA"]:
            patchId = dataset[0]
            self.assertTrue(self.butler.datasetExists("PatchOut", patchId))
            self.assertEqual(self.butler.get("PatchOut", patchId),
                             butlerTests.MetricsExample(data=(dataset[1] + inB)))

    def testRunTestQuantumVisitMockRun(self):
        task = VisitTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"visit": 102})
        data = self._makeVisitTestData(dataId)

        quantum = makeQuantum(task, self.butler, dataId,
                              {key: dataId for key in {"a", "b", "outA", "outB"}})
        run = runTestQuantum(task, self.butler, quantum, mockRun=True)

        # Can we use the mock to verify that task.run got called with the
        # correct inputs?
        run.assert_called_once_with(a=butlerTests.MetricsExample(data=data["VisitA"]),
                                    b=butlerTests.MetricsExample(data=data["VisitB"]))

    def testRunTestQuantumPatchMockRun(self):
        task = PatchTask()

        dataId = butlerTests.expandUniqueId(self.butler, {"tract": 42})
        data = self._makePatchTestData(dataId)

        quantum = makeQuantum(task, self.butler, dataId, {
            # Use lists, not sets, to ensure order agrees with test assertion
            "a": [dataset[0] for dataset in data["PatchA"]],
            "b": dataId,
            "out": [dataset[0] for dataset in data["PatchA"]],
        })
        run = runTestQuantum(task, self.butler, quantum, mockRun=True)

        # Can we use the mock to verify that task.run got called with the
        # correct inputs?
        run.assert_called_once_with(
            a=[butlerTests.MetricsExample(data=dataset[1]) for dataset in data["PatchA"]],
            b=butlerTests.MetricsExample(data=data["PatchB"][0][1])
        )

    def testRunTestQuantumPatchOptionalInput(self):
        config = PatchConfig()
        config.doUseB = False
        task = PatchTask(config=config)

        dataId = butlerTests.expandUniqueId(self.butler, {"tract": 42})
        data = self._makePatchTestData(dataId)

        quantum = makeQuantum(task, self.butler, dataId, {
            # Use lists, not sets, to ensure order agrees with test assertion
            "a": [dataset[0] for dataset in data["PatchA"]],
            "out": [dataset[0] for dataset in data["PatchA"]],
        })
        run = runTestQuantum(task, self.butler, quantum, mockRun=True)

        # Can we use the mock to verify that task.run got called with the
        # correct inputs?
        run.assert_called_once_with(
            a=[butlerTests.MetricsExample(data=dataset[1]) for dataset in data["PatchA"]]
        )

    def testAssertValidOutputPass(self):
        task = VisitTask()

        inA = butlerTests.MetricsExample(data=[1, 2, 3])
        inB = butlerTests.MetricsExample(data=[4, 0, 1])
        result = task.run(inA, inB)

        # should not throw
        assertValidOutput(task, result)

    def testAssertValidOutputMissing(self):
        task = VisitTask()

        def run(a, b):
            return Struct(outA=a)
        task.run = run

        inA = butlerTests.MetricsExample(data=[1, 2, 3])
        inB = butlerTests.MetricsExample(data=[4, 0, 1])
        result = task.run(inA, inB)

        with self.assertRaises(AssertionError):
            assertValidOutput(task, result)

    def testAssertValidOutputSingle(self):
        task = PatchTask()

        def run(a, b):
            return Struct(out=b)
        task.run = run

        inA = butlerTests.MetricsExample(data=[1, 2, 3])
        inB = butlerTests.MetricsExample(data=[4, 0, 1])
        result = task.run([inA], inB)

        with self.assertRaises(AssertionError):
            assertValidOutput(task, result)

    def testAssertValidOutputMultiple(self):
        task = VisitTask()

        def run(a, b):
            return Struct(outA=[a], outB=b)
        task.run = run

        inA = butlerTests.MetricsExample(data=[1, 2, 3])
        inB = butlerTests.MetricsExample(data=[4, 0, 1])
        result = task.run(inA, inB)

        with self.assertRaises(AssertionError):
            assertValidOutput(task, result)

    def testSkypixHandling(self):
        task = SkyPixTask()

        dataId = {"htm7": 157227}  # connection declares skypix, but Butler uses htm7
        data = butlerTests.MetricsExample(data=[1, 2, 3])
        self.butler.put(data, "PixA", dataId)

        quantum = makeQuantum(task, self.butler, dataId, {key: dataId for key in {"a", "out"}})
        run = runTestQuantum(task, self.butler, quantum, mockRun=True)

        # PixA dataset should have been retrieved by runTestQuantum
        run.assert_called_once_with(a=data)


class MyMemoryTestCase(lsst.utils.tests.MemoryTestCase):
    pass


def setup_module(module):
    lsst.utils.tests.init()


if __name__ == "__main__":
    lsst.utils.tests.init()
    unittest.main()
