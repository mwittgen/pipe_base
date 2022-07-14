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
from __future__ import annotations

__all__ = ("PipelineGraph",)

from collections.abc import Iterable
import dataclasses
from typing import TypeVar, Generic, Union, TYPE_CHECKING

from .connections import iterConnections
from . import connectionTypes as cT

if TYPE_CHECKING:
    from .pipeline import TaskDef


_R = TypeVar("_R", bound=Union[cT.Input, cT.InitInput, cT.PrerequisiteInput])
_W = TypeVar("_W", bound=Union[cT.Output, cT.InitOutput])


@dataclasses.dataclass
class TaskVertex(Generic[_R, _W]):
    task_def: TaskDef
    inputs: dict[str, ReadEdge[_R]] = dataclasses.field(default_factory=dict)
    outputs: dict[str, WriteEdge[_W]] = dataclasses.field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.task_def.label

    @classmethod
    def from_task_def(
        cls,
        task_def: TaskDef,
        input_types: Iterable[str] = ("inputs", "initInputs", "prerequisiteInputs"),
        output_types: Iterable[str] = ("outputs", "initOutputs"),
    ) -> TaskVertex[_R, _W]:
        result = cls(task_def)
        input_connection: _R
        for input_connection in iterConnections(task_def.connections, input_types):
            parent_dataset_type_name, _, component = input_connection.name.partition(".")
            result.inputs[parent_dataset_type_name] = ReadEdge(
                task_def.label, parent_dataset_type_name, component, input_connection
            )
        output_connection: _W
        for output_connection in iterConnections(task_def.connections, output_types):
            result.outputs[output_connection.name] = WriteEdge(
                task_def.label, output_connection.name, output_connection
            )
        return result


@dataclasses.dataclass
class DatasetTypeVertex(Generic[_R, _W]):
    name: str
    producer: WriteEdge[_W] | None
    consumers: dict[str, ReadEdge[_R]] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_write_edge(cls, edge: WriteEdge[_W]) -> DatasetTypeVertex:
        return cls(edge.dataset_type_name, edge, {})

    @classmethod
    def from_read_edge(cls, edge: ReadEdge[_R]) -> DatasetTypeVertex:
        return cls(edge.parent_dataset_type_name, None, {edge.task_label: edge})


@dataclasses.dataclass
class ReadEdge(Generic[_R]):
    task_label: str
    parent_dataset_type_name: str
    component: str
    connection: _R


@dataclasses.dataclass
class WriteEdge(Generic[_W]):
    task_label: str
    dataset_type_name: str
    connection: _W


@dataclasses.dataclass
class PipelineGraph(Generic[_R, _W]):

    tasks: dict[str, TaskVertex[_R, _W]] = dataclasses.field(default_factory=dict)
    dataset_types: dict[str, DatasetTypeVertex[_R, _W]] = dataclasses.field(default_factory=dict)

    @classmethod
    def build_init(
        cls: type[PipelineGraph[cT.InitInput, cT.InitOutput]], task_defs: Iterable[TaskDef]
    ) -> PipelineGraph[cT.InitInput, cT.InitOutput]:
        return cls.build(task_defs, input_types=("initInputs",), output_types=("initOutputs",))

    @classmethod
    def build_runtime(
        cls: type[PipelineGraph[cT.Input | cT.PrerequisiteInput, cT.Output]], task_defs: Iterable[TaskDef]
    ) -> PipelineGraph[cT.Input | cT.PrerequisiteInput, cT.Output]:
        return cls.build(task_defs, input_types=("inputs", "prerequisiteInputs"), output_types=("outputs",))

    @classmethod
    def build(
        cls,
        task_defs: Iterable[TaskDef],
        input_types: Iterable[str] = ("inputs", "initInputs", "prerequisiteInputs"),
        output_types: Iterable[str] = ("outputs", "initOutputs"),
    ) -> PipelineGraph:
        tasks: dict[str, TaskVertex] = {}
        dataset_types: dict[str, DatasetTypeVertex] = {}
        for task_def in task_defs:
            task_vertex = TaskVertex.from_task_def(
                task_def, input_types=input_types, output_types=output_types
            )
            for write_edge in task_vertex.outputs.values():
                dataset_types[write_edge.dataset_type_name] = DatasetTypeVertex.from_write_edge(write_edge)
            tasks[task_def.label] = task_vertex
        for task_vertex in tasks.values():
            for read_edge in task_vertex.inputs.values():
                if (dataset_type_vertex := dataset_types.get(read_edge.parent_dataset_type_name)) is None:
                    dataset_type_vertex = DatasetTypeVertex.from_read_edge(read_edge)
                    dataset_types[dataset_type_vertex.name] = dataset_type_vertex
        return cls(tasks, dataset_types)

    def sorted(self) -> PipelineGraph[_R, _W]:
        result = PipelineGraph[_R, _W]()
        for dataset_type in self.dataset_types.values():
            if dataset_type.producer is None:
                result.dataset_types[dataset_type.name] = dataset_type
        tasks_to_do = set(self.tasks.keys())
        while tasks_to_do:
            unblocked_tasks: list[str] = []
            unblocked_task_outputs: list[str] = []
            for task_label in tasks_to_do:
                if self.tasks[task_label].inputs.keys() <= result.dataset_types.keys():
                    unblocked_tasks.append(task_label)
                    unblocked_task_outputs.extend(self.tasks[task_label].outputs.keys())
            if not unblocked_tasks:
                raise ValueError(f"Cycle encountered involving {tasks_to_do}.")
            unblocked_tasks.sort()
            unblocked_task_outputs.sort()
            for task_label in unblocked_tasks:
                result.tasks[task_label] = self.tasks[task_label]
            for dataset_type_name in unblocked_task_outputs:
                result.dataset_types[dataset_type_name] = self.dataset_types[dataset_type_name]
            tasks_to_do.difference_update(unblocked_tasks)
        return result
