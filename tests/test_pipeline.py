# This file is part of pipe_base.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (http://www.lsst.org).
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Simple unit test for Pipeline.
"""

import pickle
import textwrap
import unittest

import lsst.utils.tests
from lsst.pipe.base import Pipeline, PipelineDatasetTypes, TaskDef
from lsst.pipe.base.tests.simpleQGraph import AddTask, makeSimplePipeline


class PipelineTestCase(unittest.TestCase):
    """A test case for TaskDef and Pipeline."""

    def testTaskDef(self):
        """Tests for TaskDef structure"""
        task1 = TaskDef(taskClass=AddTask, config=AddTask.ConfigClass())
        self.assertIn("Add", task1.taskName)
        self.assertIsInstance(task1.config, AddTask.ConfigClass)
        self.assertIsNotNone(task1.taskClass)
        self.assertEqual(task1.label, "add_task")
        task1a = pickle.loads(pickle.dumps(task1))
        self.assertEqual(task1, task1a)

    def testEmpty(self):
        """Creating empty pipeline"""
        pipeline = Pipeline("test")
        self.assertEqual(len(pipeline), 0)

    def testInitial(self):
        """Testing constructor with initial data"""
        pipeline = makeSimplePipeline(2)
        self.assertEqual(len(pipeline), 2)
        expandedPipeline = list(pipeline.toExpandedPipeline())
        self.assertEqual(expandedPipeline[0].taskName, "lsst.pipe.base.tests.simpleQGraph.AddTask")
        self.assertEqual(expandedPipeline[1].taskName, "lsst.pipe.base.tests.simpleQGraph.AddTask")
        self.assertEqual(expandedPipeline[0].taskClass, AddTask)
        self.assertEqual(expandedPipeline[1].taskClass, AddTask)
        self.assertEqual(expandedPipeline[0].label, "task0")
        self.assertEqual(expandedPipeline[1].label, "task1")

    def testParameters(self):
        """Test that parameters can be set and used to format"""
        pipeline_str = textwrap.dedent(
            """
            description: Test Pipeline
            parameters:
               testValue: 5
            tasks:
              add:
                class: test_pipeline.AddTask
                config:
                  addend: parameters.testValue
        """
        )
        # verify that parameters are used in expanding a pipeline
        pipeline = Pipeline.fromString(pipeline_str)
        expandedPipeline = list(pipeline.toExpandedPipeline())
        self.assertEqual(expandedPipeline[0].config.addend, 5)

        # verify that a parameter can be overridden on the "command line"
        pipeline.addConfigOverride("parameters", "testValue", 14)
        expandedPipeline = list(pipeline.toExpandedPipeline())
        self.assertEqual(expandedPipeline[0].config.addend, 14)

        # verify that a non existing parameter cant be overridden
        with self.assertRaises(ValueError):
            pipeline.addConfigOverride("parameters", "missingValue", 17)

        # verify that parameters does not support files or python overrides
        with self.assertRaises(ValueError):
            pipeline.addConfigFile("parameters", "fakeFile")
        with self.assertRaises(ValueError):
            pipeline.addConfigPython("parameters", "fakePythonString")

    def testSerialization(self):
        pipeline = makeSimplePipeline(2)
        dump = str(pipeline)
        load = Pipeline.fromString(dump)
        self.assertEqual(pipeline, load)

    def test_initOutputNames(self):
        """Test for PipelineDatasetTypes.initOutputNames method."""
        pipeline = makeSimplePipeline(3)
        dsType = set(PipelineDatasetTypes.initOutputNames(pipeline))
        expected = {
            "packages",
            "add_init_output1",
            "add_init_output2",
            "add_init_output3",
            "task0_config",
            "task1_config",
            "task2_config",
        }
        self.assertEqual(dsType, expected)


class MyMemoryTestCase(lsst.utils.tests.MemoryTestCase):
    pass


def setup_module(module):
    lsst.utils.tests.init()


if __name__ == "__main__":
    lsst.utils.tests.init()
    unittest.main()
