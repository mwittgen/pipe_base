.. TODO DM-11673 This topic should be edited into the modernized topic-based documentation style.
.. See comments: https://github.com/lsst/pipe_base/pull/37/files#diff-292ab354e767bb472ec66e422ca6e375

.. _creating-a-task:

###############
Creating a task
###############

This document describes how to write a data processing task.
For an introduction to data processing tasks, please read :doc:`task-framework-overview`.
It also helps to have a basic understanding of data repositories and how to use the butler to read and write data (to be written; for now read existing tasks to see how it is done).

After reading this document you may wish to read :doc:`creating-a-command-line-task`.

.. _creating-a-task-intro:

Introduction
============

Tasks are subclasses of `lsst.pipe.base.Task` in general or `lsst.pipe.base.CmdLineTask` for command-line tasks.

Tasks are constructed by calling ``__init__`` with the :ref:`task configuration <creating-a-task-configuration>`.
Occasionally additional arguments are required (see the task's documentation for details).
`lsst.pipe.base.Task` has a few other arguments that are usually only specified when a task is created as a subtask of another task; you will probably never have to specify them yourself.
(Command-line tasks are often constructed and run by calling `lsst.pipe.base.parseAndRun`, as described in :doc:`creating-a-command-line-task`.)

Tasks typically have a ``run`` method that executes the task's main function.
See :ref:`creating-a-task-class-methods` for more information.

.. _creating-a-task-configuration:

Configuration
=============

Every task requires a configuration: a task-specific set of configuration parameters.
The configuration is read-only; once you construct a task, the same configuration will be used to process all data with that task.
This makes the data processing more predictable: it does not depend on the order in which items of data are processed.

The task's configuration is specified using a task-specific subclass of `lsst.pex.config.Config`.
The task class specifies its configuration class using class variable `ConfigClass`.
If the task has no configuration parameters then it may use `lsst.pex.config.Config` as its configuration class.

Some important details of configurations:

- Supply useful defaults for all config parameters if at all possible.
  Your task will be much easier to use if the default configuration usually suffices.

- Document each field of the configuration carefully.
  Pretend you don't know anything about your task and ask yourself what you would need to be told to change the parameter.
  What does the parameter do and why might you change it?
  What units does it have?

- Subtasks are specified in your configuration as fields of type `lsst.pex.config.ConfigurableField` or (less commonly) `lsst.pex.config.RegistryField`.
  This allows subtasks to be :doc:`retargeted <command-line-task-retargeting-howto>` (replaced with a variant subtask).
  For more information see :ref:`creating-a-task-subtasks`.

  `~lsst.pipe.tasks.exampleStatsTasks.ExampleSigmaClippedStatsTask` uses configuration class `~lsst.pipe.tasks.exampleStatsTasks.ExampleSigmaClippedStatsConfig`:

  .. code-block:: python

     class ExampleSigmaClippedStatsConfig(pexConfig.Config):
         """Configuration for ExampleSigmaClippedStatsTask.
         """
         badMaskPlanes = pexConfig.ListField(
             dtype=str,
             doc="Mask planes that, if set, indicate the associated pixel should "
             "not be included when the calculating statistics.",
             default=("EDGE",),
         )
         numSigmaClip = pexConfig.Field(
             doc="number of sigmas at which to clip data",
             dtype=float,
             default=3.0,
         )
         numIter = pexConfig.Field(
             doc="number of iterations of sigma clipping",
             dtype=int,
             default=2,
         )

The configuration class is specified as ``ExampleSigmaClippedStatsTask`` class variable ``ConfigClass``, as described in :ref:`creating-a-task-class-variables`.

Here is the config for ``ExampleCmdLineTask``, a task that calls one subtask named ``stats``; notice the `lsst.pex.config.ConfigurableField`:

.. code-block:: python

   class ExampleCmdLineConfig(pexConfig.Config):
       """Configuration for ExampleCmdLineTask.
       """
       stats = pexConfig.ConfigurableField(
           doc="Subtask to compute statistics of an image",
           target=ExampleSigmaClippedStatsTask,
       )
       doFail = pexConfig.Field(
           doc="Raise an lsst.base.TaskError exception when processing each image? "
           + "This allows one to see the effects of the --doraise command line flag",
           dtype=bool,
           default=False,
       )

.. _creating-a-task-class-variables:

Class variables
===============

Tasks require several class variables to function:

- ``ConfigClass``: the :ref:`configuration class <creating-a-task-configuration>` used by the task.

- ``_DefaultName``: a string used as the default name for the task.
  This is required for a command-line task (`~pipe.base.cmdLineTask.CmdLineTask`), and strongly recommended for other tasks because it makes them easier to construct for unit tests.
  Note that when a task creates a subtask, it ignores the subtask's ``_DefaultName`` and assigns the name of the config parameter as the subtask's name.
  For example ``exampleCmdLineTask.ExampleCmdLineConfig`` creates the statistics subtask with name ``stats`` because the config field for that subtask is ``stats = lsst.pex.config.ConfigurableField(...)``.

  Task names are used for the hierarchy of task and subtask metadata.
  Also, for command-line tasks the name is used as a component of the of the dataset type for saving the task's configuration and metadata; see :ref:`creating-a-command-line-task-persisting-config-and-metadata` for more information.

- ``RunnerClass``: only needed for command-line tasks; see :doc:`creating-a-command-line-task` for more information.

- ``canMultiprocess``: only needed for command-line tasks; see :doc:`creating-a-command-line-task` for more information.

Here are the class variables for ``ExampleCmdLineTask``:

.. code-block:: python

   ConfigClass = ExampleCmdLineConfig
   _DefaultName = "exampleTask"

.. _creating-a-task-class-methods:

Methods
=======

Tasks have the following important methods:

- :ref:`__init__ <creating-a-task-class-init-method>`: construct and initialize a task.
- :ref:`run <creating-a-task-class-run-method>`: process one item of data.

These methods are described in more depth below.

.. _creating-a-task-class-init-method:

The ``__init__`` method
-----------------------

Use the ``__init__`` method (task constructor) to do the following:

- Call the parent task's ``__init__`` method
- Make subtasks by calling ``self.makeSubtask(name)``, where ``name`` is the name of a field of type `lsst.pex.config.ConfigurableField` in your :ref:`task's configuration <creating-a-task-configuration>`.
- Make a schema if your task uses an `lsst.afw.table`.
  For an example of such a task `lsst.pipe.tasks.calibrate.CalibrateTask`.
- Initialize any other instance variables your task needs.

Here is ``exampleCmdLineTask.ExampleCmdLineTask.__init__``:

.. code-block:: python

   def __init__(self, *args, **kwargs):
       """Construct an ExampleCmdLineTask
       Call the parent class constructor and make the "stats" subtask from the config field of the same name.
       """
       pipeBase.CmdLineTask.__init__(self, *args, **kwargs)
       self.makeSubtask("stats")

That task creates a subtask named ``stats`` to compute image statistics.
Here is the ``__init__`` method for the default version of the `stats` subtask:

exampleTask.ExampleSigmaClippedStatsTask, which is slightly more interesting:

.. code-block:: python

   def __init__(self, *args, **kwargs):
       """!Construct an ExampleSigmaClippedStatsTask
       The init method may compute anything that that does not require data.
       In this case we create a statistics control object using the config
       (which cannot change once the task is created).
       """
       pipeBase.Task.__init__(self, *args, **kwargs)
       self._badPixelMask = MaskU.getPlaneBitMask(self.config.badMaskPlanes)
       self._statsControl = afwMath.StatisticsControl()
       self._statsControl.setNumSigmaClip(self.config.numSigmaClip)
       self._statsControl.setNumIter(self.config.numIter)
       self._statsControl.setAndMask(self._badPixelMask)

This creates a binary mask identifying bad pixels in the mask plane and an `lsst.afw.math.StatisticsControl`, specifying how statistics are computed.
Both of these are constants, and thus are the same for each invocation of the ``run`` method; this is strongly recommended, as explained in the next section.

.. _creating-a-task-class-run-method:

Task execution methods
----------------------

The run method
^^^^^^^^^^^^^^

All tasks are required to have a ``run`` method which acts as their primary point of entry.
This method takes, as explicit arguments, everything that the task needs to perform one unit of execution (for example, processing a single image), and returns the result to the caller.
The ``run`` method should not perform I/O, and, in particular, should not be expected to have access to the Data Butler for storing and retrieving data.
Instead, results are returned as an `lsst.pipe.base.struct.Struct` object, with a named field for each item of data.
This is safer than returning a tuple of items, and allows adding fields without affecting existing code.

.. note::

   In some, unusual, circumstances, it may be necessary for ``run`` to have access to the Data Butler, or for a task not to provide a ``run`` method.
   In code released by DM, these cases should be approved by the DM Change Control Board through the `RFC process <https://developer.lsst.io/communications/rfc.html>`_.

If your task's processing can be divided into logical units, then we recommend that you provide methods for each unit.
``run`` can then call each method to do its work.
This allows your task to be more easily adapted: a subclass can override just a few methods.
Any method that is likely to take significant time or memory should be preceded by this python decorator: `lsst.utils.timer.timeMethod`.
This automatically records the execution time and memory of the method in the task's ``metadata`` attribute.

We strongly recommend that you make your task stateless, by not using instance variables as part of your data processing.
Pass data between methods by calling and returning it.
This makes the task much easier to reason about, since processing one item of data cannot affect future items of data.

The runDataRef method
^^^^^^^^^^^^^^^^^^^^^

In addition to ``run``, many tasks have a ``runDataRef`` method which accepts a Butler data reference; loads appropriate data from it; calls ``run``; and writes the results back to the Butler.
This is required for all command-line tasks.

Examples
^^^^^^^^

The example ``exampleCmdLineTask.ExampleCmdLineTask`` is so simple that it needs no other methods; ``runDataRef`` does everything:

.. code-block:: python

   @lsst.utils.timer.timeMethod
   def runDataRef(self, dataRef):
       """Compute a few statistics on the image plane of an exposure
       @param dataRef: data reference for a calibrated science exposure ("calexp")
       @return a pipeBase Struct containing:
       - mean: mean of image plane
       - meanErr: uncertainty in mean
       - stdDev: standard deviation of image plane
       - stdDevErr: uncertainty in standard deviation
       """
       self.log.info("Processing data ID %s" % (dataRef.dataId,))
       if self.config.doFail:
           raise pipeBase.TaskError("Raising TaskError by request (config.doFail=True)")
       # Unpersist the raw exposure pointed to by the data reference
       rawExp = dataRef.get("raw")
       maskedImage = rawExp.getMaskedImage()
       # Support extra debug output.
       # -
       import lsstDebug
       display = lsstDebug.Info(__name__).display
       if display:
           frame = 1
           mtv(rawExp, frame=frame, title="exposure")
       # return the pipe_base Struct that is returned by self.stats.run
       return self.stats.run(maskedImage)

The statistics are actually computed by the ``stats`` subtask.
Here is the ``run`` method for the default version of that task: ``exampleTask.ExampleSigmaClippedStatsTask.run``:

.. code-block:: python

   @lsst.utils.timer.timeMethod
   def run(self, maskedImage):
       """!Compute and return statistics for a masked image
       @param[in] maskedImage: masked image (an lsst::afw::MaskedImage)
       @return a pipeBase Struct containing:
       - mean: mean of image plane
       - meanErr: uncertainty in mean
       - stdDev: standard deviation of image plane
       - stdDevErr: uncertainty in standard deviation
       """
       statObj = afwMath.makeStatistics(maskedImage, afwMath.MEANCLIP | afwMath.STDEVCLIP | afwMath.ERRORS,
                                        self._statsControl)
       mean, meanErr = statObj.getResult(afwMath.MEANCLIP)
       stdDev, stdDevErr = statObj.getResult(afwMath.STDEVCLIP)
       self.log.info("clipped mean=%0.2f; meanErr=%0.2f; stdDev=%0.2f; stdDevErr=%0.2f" %
                     (mean, meanErr, stdDev, stdDevErr))
       return pipeBase.Struct(
           mean=mean,
           meanErr=meanErr,
           stdDev=stdDev,
           stdDevErr=stdDevErr,
       )

.. _creating-a-task-debug-variables:

Debug variables
===============

Debug variables are variables the user may set while running your task, to enable additional debug output.
To have your task support debug variables, have it import ``lsstDebug`` and call ``lsstDebug.Info(__name__).varname`` to get the debug variable ``varname`` specific to your task.
If you look for a variable the user has not specified, it will have a value of `False`.
For example, to look for a debug variable named "display":

.. code-block:: python

   import lsstDebug
   display = lsstDebug.Info(__name__).display
   if display:
      # ...
      pass

.. FIXME create link when lsstDebug documentation is ready.
.. See \ref baseDebug for more information about debug variables, including how to specify them while running a command-line task.

.. _creating-a-task-docs:

Documentation
=============

To be written.

.. _creating-a-task-subtasks:

Subtasks
========

Each subtask is specified in the configuration as a field of type `lsst.pex.config.ConfigurableField` or (less commonly) `lsst.pex.config.RegistryField`.
There are advantages to each:

- `lsst.pex.config.ConfigurableField` advantages:

  - It is easier for the user to override settings of the subtask; simply use dotted name notation:

    .. code-block:: python

       config.configurableSubtask.subtaskParam1 = ...

    In contrast, to override configuration for a subtask specified as an `lsst.pex.config.RegistryField` you must either specify the name of the subtask to configure:

    .. code-block:: python

       config.registrySubtask[nameOfSelectedSubtask].subtaskParam1 = ...

    Or use the `active` attribute to modify the configuration of the currently selected (active) subtask:

    .. code-block:: python

       config.registrySubtask.active.subtaskParam1 = ...

- `lsst.pex.config.RegistryField` advantages:

  - You can specify overrides for any registered subtask and they are remembered if you retarget subtasks.
    In comparison if the subtask is specified as an `lsst.pex.config.ConfigurableField` then you can only override parameters for the currently retargeted subtask, and all overrides are lost each time you retarget.
    Thus using an `lsst.pex.config.RegistryField` offers the opportunity to specify suitable overrides for more than one variant subtask, making it safer for the user to use those variants.
    Of course this can get out of hand if there are many variants, so users should not assume that all variants have suitable overrides.

  - Retargeting a subtask can be done using :option:`--config` on the command line, as long as the module containing the desired subtask has been imported:

    .. code-block:: python

       config.registrySubtask.name = "foo"

    By comparison, a subtask specified as an `lsst.pex.config.ConfigurableField` can only be retargeted from a config override file (e.g. using :option:`--config-file`, never :option:`--config`):

    .. code-block:: python

       from ... import FooTask
       config.configurableSubtask.retarget(FooTask)

  - Variants subtasks are kept together in one registry, making it easier to find them.

Our recommendation: if you anticipate that users will often wish to override the subtask with a variant, then use an `lsst.pex.config.RegistryField`.
Otherwise use an `lsst.pex.config.ConfigurableField` to keep config overrides simpler and easier to read.

For example PSF determiners and star selectors are perhaps best specified using `lsst.pex.config.RegistryField` because there are several variants users may wish to select from.
However, calibration and instrument signature removal are best specified using  `lsst.pex.config.ConfigurableField`  because (for a given camera) there is likely to be only one logical variant, and that variant is specified in a camera-specific configuration override file, so the user need not specify it.

Variant tasks
=============

When there are (or are expected to be) different versions of a given task, those tasks should inherit from an abstract base class that defines the interface and is itself a subclass of `lsst.pipe.base.Task`.
Star selectors (`lsst.meas.algorithms.BaseStarSelectorTask`) and PSF determiners (`lsst.meas.algorithms.BasePsfDeterminerTask`) are two examples of tasks with multiple variants.
The abstract base class should be written using `abc.ABC` or `abc.ABCMeta`.
The same module that defines the abstract base class should also define a registry, using `lsst.pex.config.RegistryField`, and all implementations should register themselves with that registry.
Examples include `lsst.meas.algorithms.starSelectorRegistry` and `lsst.meas.algorithms.psfDeterminerRegistry`.
