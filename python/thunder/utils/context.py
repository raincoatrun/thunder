""" Simple wrapper for a Spark Context to provide loading functionality """

import os
import json
from numpy import asarray, floor, ceil, shape, arange
from scipy.io import loadmat
from pyspark import SparkContext
from thunder.utils import DataSets, checkparams
from thunder.rdds.series import SeriesLoader
from thunder.rdds.images import ImagesLoader


class ThunderContext():
    """
    Wrapper for a Spark Context

    Attributes
    ----------
    `_sc` : SparkContext
        Spark context for Spark functionality
    """

    def __init__(self, sparkcontext):
        self._sc = sparkcontext

    @classmethod
    def start(cls, *args, **kwargs):
        """Starts a ThunderContext using the same arguments as SparkContext"""
        return ThunderContext(SparkContext(*args, **kwargs))

    def loadSeries(self, datafile, nkeys=None, nvalues=None, inputformat='binary', minPartitions=None,
                   conffile='conf.json'):
        """
        Loads a Series RDD from data stored as text or binary files.

        Parameters
        ----------
        datafile: string
            path to single file or directory. If directory, will be expected to contain multiple *.txt (if
            text) or *.bin (if binary) data files.

        nkeys: int, optional
            dimensionality of data keys. (For instance, (x,y,z) keyed data for 3-dimensional image timeseries data.)
            For text data, number of keys must be specified in this parameter; for binary data, number of keys must be
            specified either in this parameter or in a configuration file named by the 'conffile' argument if this
            parameter is not set.

        nvalues: int, optional
            Number of values expected to be read. For binary data, nvalues must be specified either in this parameter
            or in a configuration file named by the 'conffile' argument if this parameter is not set.

        inputformat: string, optional, default = 'binary'
            Format of data to be read. Must be either 'text' or 'binary'.

        minPartitions: int, optional
            Explicitly specify minimum number of Spark partitions to be generated from this data. Used only for
            text data. Default is to use minParallelism attribute of Spark context object.

        conffile: string, optional, default 'conf.json'
            Path to JSON file with configuration options including 'nkeys' and 'nvalues'. If a file is not found at the
            given path, then the base directory given in 'datafile' will also be checked. Parameters specified as
            explicit arguments to this method take priority over those found in conffile if both are present.
        """
        checkparams(inputformat, ['text', 'binary'])

        loader = SeriesLoader(self._sc, minPartitions=minPartitions)

        if inputformat.lower() == 'text':
            data = loader.fromText(datafile, nkeys=nkeys)
        else:
            # must be either 'text' or 'binary'
            data = loader.fromBinary(datafile, conffilename=conffile, nkeys=nkeys, nvalues=nvalues)

        return data

    def loadSeriesLocal(self, datafile, nkeys=3, nvalues=None, inputformat='npy', minPartitions=None):

        checkparams(inputformat, ['mat', 'npy'])
        loader = SeriesLoader(self._sc, nkeys=nkeys, nvalues=nvalues, minPartitions=minPartitions)

        if inputformat.lower() == 'mat':
            data = loader.fromMatLocal(datafile)
        else:
            data = loader.fromNpyLocal(datafile)

        return data

    def loadImages(self, datafile, dims=None, inputformat='stack', startidx=None, stopidx=None):
        """
        Loads an Images RDD from data stored as a binary image stack, tif, or png files.

        Parameters
        ----------
        datafile: string
            path to single file or directory. If directory, will be expected to contain multiple *.stack, *.tif, or
            *.png files, for 'stack', 'tif', and 'png' inputformats, respectively.

        dims: tuple of ints, optional
            Gives expected shape of a single file of input stack data (for example, x,y,z dimensions for 3d image
            files.) Expected to be in numpy 'F' (Fortran/Matlab; column-major) convention. Used only for 'stack'
            inputformat.

        inputformat: string, optional, default = 'stack'
            Format of data to be read. Must be either 'stack', 'tif', or 'png'.
        """
        checkparams(inputformat, ['stack', 'png', 'tif', 'tif-stack'])
        loader = ImagesLoader(self._sc)

        if inputformat.lower() == 'stack':
            data = loader.fromStack(datafile, dims, startidx=startidx, stopidx=stopidx)
        elif inputformat.lower() == 'tif':
            data = loader.fromTif(datafile, startidx=startidx, stopidx=stopidx)
        elif inputformat.lower() == 'tif-stack':
            data = loader.fromMultipageTif(datafile, startidx=startidx, stopidx=stopidx)
        else:
            data = loader.fromPng(datafile)

        return data

    def makeExample(self, dataset, **opts):
        """
        Make an example data set for testing analyses
        see DataSets

        Parameters
        ----------
        dataset : str
            Which dataset to generate

        Returns
        -------
        data : RDD of (tuple, array) pairs
            Generated dataset
        """

        return DataSets.make(self._sc, dataset, **opts)

    def loadExample(self, dataset):
        """
        Load a local example data set for testing analyses

        Parameters
        ----------
        dataset : str
            Which dataset to load

        Returns
        -------
        data : RDD of (tuple, array) pairs
            Generated dataset
        """

        path = os.path.dirname(os.path.realpath(__file__))

        if dataset == "iris":
            return self.loadSeries(os.path.join(path, 'data/iris.txt'), inputformat="text", minPartitions=1, nkeys=3)
        elif dataset == "fish":
            return self.loadSeries(os.path.join(path, 'data/fish.txt'), inputformat="text", minPartitions=1, nkeys=3)
        else:
            raise NotImplementedError("Dataset '%s' not found" % dataset)

    def loadExampleEC2(self, dataset):
        """
        Load an example data set from EC2

        Parameters
        ----------
        dataset : str
            Which dataset to load

        Returns
        -------
        data : RDD of (tuple, array) pairs
            Generated dataset

        params : Tuple or numpy array
            Parameters or metadata for dataset
        """

        if 'ec' not in self._sc.master:
            raise Exception("must be running on EC2 to load this example data sets")
        elif dataset == "zebrafish-optomotor-response":
            path = 'zebrafish.datasets/optomotor-response/1/'
            data = self.loadSeries("s3n://" + path + 'data/dat_plane*.txt', inputformat='text', minPartitions=1000)
            paramfile = self._sc.textFile("s3n://" + path + "params.json")
            params = json.loads(paramfile.first())
            modelfile = asarray(params['trials'])
            return data, modelfile
        else:
            raise NotImplementedError("dataset '%s' not availiable" % dataset)

    def loadBinaryLocal(self, datafile, nvalues, nkeys, format, keyfile=None, method=None):
        """
        Load data from a local binary file
        """

        raise NotImplementedError

    def loadArrayLocal(self, values, keys=None, method=None):
        """
        Load data from local arrays
        """

        raise NotImplementedError

    def loadMatLocal(self, datafile, varname, keyfile=None, filter=None, minPartitions=1):
        """
        Load data from a local MAT file, from a variable containing
        either a 1d or 2d matrix, into an RDD of (key,value) pairs.
        Each row of the input matrix will become the value of each record.

        Keys can be provided in an extra MAT file containing a variable 'keys'.
        If not provided, linear indices will be used as keys.

        Parameters
        ----------
        datafile : str
            MAT file to import

        varname : str
            Variable name to load from MAT file

        keyfile : str
            MAT file to import with keys (must contain a variable 'keys')

        filter : str, optional, default = None (no preprocessing)
            Which preprocessing to perform

        minPartitions : Int, optional, default = 1
            Number of partitions for data

        """

        data = loadmat(datafile)[varname]
        if data.ndim > 2:
            raise IOError('input data must be one or two dimensional')
        if keyfile:
            keys = map(lambda x: tuple(x), loadmat(keyfile)['keys'])
        else:
            keys = arange(1, shape(data)[0]+1)

        rdd = self._sc.parallelize(zip(keys, data), minPartitions)

        return preprocess(rdd, method=filter)


def preprocess(data, method=None):

    if method:
        preprocessor = PreProcessor(method)
        return data.mapValues(preprocessor.get)
    else:
        return data