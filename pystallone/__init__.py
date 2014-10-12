'''
PyStallone
==========

This package provides a python wrapper to run the Java Stallone library.

The API variable is the main entry point into the Stallone API factory. This
class has factories and utility classes for wrapping primitive arrays, performing
io, constructing (hidden/projected) Markov models and various related tasks.


Examples
========

Datatypes
---------
create a double vector and assigning values:
>>> from pystallone import stallone as st
>>> x = st.api.API.doublesNew.array(10) # create double array with 10 elements
>>> x.set(5, 23.0) # set index 5 to 23.0
>>> print(x)
0.0     0.0     0.0     0.0     0.0     23.0     0.0     0.0     0.0     0.0

# TODO: add more examples (doctests)

Algebra
-------

Markov modeling
---------------


Created on 15.10.2013
moved from emma2 on 8.8.2014

@author: marscher
'''

from jpype import \
 startJVM as _startJVM, \
 isJVMStarted, \
 shutdownJVM, \
 getDefaultJVMPath, \
 JavaException, \
 JArray, JInt, JDouble, JString, JObject, JPackage, \
 java, javax, nio as _nio

import numpy as _np
import sys as _sys
import warnings as _warnings
from ._version import get_versions

__version__ = get_versions()['version']
_64bit = _sys.maxsize > 2**32

del get_versions
del _sys

"""
types wrapped in stallone java library
"""
_supported_types = [_np.int32, _np.int64, _np.float32, _np.float64]

""" stallone java package. Should be used to access all classes in the stallone library."""
stallone = None
""" main stallone API entry point """
API = None

def startJVM(jvm = None, args = None):
    """
    semantically the same like jpype.startJVM, but appends the stallone jar to
    the (given) classpath.
    
    Parameters
    ----------
    jvm : (optional) string 
        Path to jvm (see jpype.getDefaultJVMPath), if none is given a path
        will be choosen via jpype.
    
    args : (optional) list
    list of additional jvm parameters like ['-xms', '64m'] etc.
    
    """
    import os
    import pkg_resources
    
    global stallone, API
    
    if not jvm:
        jvm = getDefaultJVMPath()

    if not os.path.exists(jvm):
        raise RuntimeError('jvm path "%s" does not exist!' % jvm)
        
    if not args:
        args = []
    
    def append_to_classpath(args):
        """
        args := args for startJVM containing classpath str
        """
        # define classpath separator
        if os.name is 'posix':
            sep = ':'
        else:
            sep = ';'
        
        # TODO: howto handle filename?
        stallone_jar = 'stallone-1.0-SNAPSHOT-jar-with-dependencies.jar'
        stallone_jar_file = pkg_resources.resource_filename('pystallone', stallone_jar)
        if not os.path.exists(stallone_jar_file):
            raise RuntimeError('stallone jar not found! Expected it here: %s' 
                           % stallone_jar_file)
        
        cp_extended = False
        n = len(args) if hasattr(args, '__len__') else 0

        arg_ind = -1
        cp_ind = -1
        
        # search for classpath definition and extend it, if found.
        for i in range(n):
            cp_ind = args[i].find('-Djava.class.path=')
            # append stallone jar to classpath
            if cp_ind != -1:
                # find end of classpath
                arg_ind = i
                p = args[i][cp_ind:].find(' ')
                end =  p if p > 0 else None
                cp_str = args[i][cp_ind:end] + sep + stallone_jar_file
                cp_extended = True
                break
        
        if not cp_extended:
            args.append('-Djava.class.path=' + stallone_jar_file)
        else:
            args[arg_ind] = cp_str
            
        return args
    
    args = append_to_classpath(args)
    _startJVM(jvm, *args)

    stallone = JPackage('stallone')
    API = stallone.api.API
    if type(API).__name__ != 'stallone.api.API$$Static':
        raise RuntimeError('Stallone package initialization borked.'
                           'Check your JAR/classpath!') 

def ndarray_to_stallone_array(pyarray, copy=True):
    """
    Convert numpy ndarrays to the corresponding wrapped type in Stallone. 
    Currently only int32 and double are supported in stallone.
    
    Parameters
    ----------
    pyarray : numpy.ndarray or scipy.sparse type one or two dimensional
    
    copy : boolean
      if false, a Java side ByteBuffer wrapping the given array buffer will
      be used to avoid a copy. This is useful for very huge data sets.
    
    Returns
    -------
    IDoubleArray or IIntArray depending on input type
    
    Note:
    -----
    scipy.sparse types will be currently converted to dense, before passing
    them to the java side!
    """
    if not isinstance(pyarray, _np.ndarray):
        raise TypeError('Only numpy arrays supported. Given type was "%s"' 
                        % type(pyarray))
    
    if pyarray.dtype not in _supported_types:
        raise TypeError('Given type %s not mapped in stallone library' 
                        % pyarray.dtype)
    
    """
    from scipy.sparse.base import issparse
    if issparse(pyarray):
        _log.warning("converting sparse object to dense for stallone.")
        pyarray = pyarray.todense()
    """
    
    shape = pyarray.shape
    dtype = pyarray.dtype
    factory = None
    cast_func = None
    
    # stallone does currently support only wrappers for int32 and float64
    if dtype == _np.float32:
        _warnings.warn("Upcasting floats to doubles!")
        pyarray = pyarray.astype(_np.float64)
    if dtype == _np.int64:
        _warnings.warn("Downcasting long to 32 bit integer."
                       " You will loose precision by doing so!")
        pyarray = pyarray.astype(_np.int32)
        
    # Pass memory to jpype and create a java array.
    # Also set corresponding factory method in stallone to wrap the array.
    if dtype == _np.float32 or dtype == _np.float64:
        factory = API.doublesNew
        cast_func = JDouble

    elif dtype == _np.int32 or dtype == _np.int64:
        factory = API.intsNew
        cast_func = JInt
        
    if not copy:
        if not pyarray.flags.c_contiguous:
            raise RuntimeError('Can only pass contiguous memory to Java!')
        jbuff = _nio.convertToDirectBuffer(pyarray)
        rows = shape[0]
        cols = 1 if len(shape) == 1 else shape[1]
        return factory.arrayFrom(jbuff, rows, cols)

    if len(shape) == 1:
        # create a JArray wrapper
        jarr = JArray(cast_func)(pyarray)
        if cast_func is JDouble:
            return factory.array(jarr)
        if cast_func is JInt:
            return factory.arrayFrom(jarr)
        raise TypeError('type not mapped to a stallone factory')

    elif len(shape) == 2:
        # TODO: use linear memory layout here, when supported in stallone
        jarr = JArray(cast_func, 2)(pyarray)
        if cast_func is JDouble:
            # for double arrays
            A = factory.array(jarr)
        elif cast_func is JInt:
            # for int 2d arrays
            A = factory.table(jarr)
        else:
            raise TypeError('type not mapped to a stallone factory')
        return A
    else:
        raise ValueError('unsupported shape:', shape)



def stallone_array_to_ndarray(stArray):
    """
    Returns
    -------
    ndarray : 
    
    
    This subclass of numpy multidimensional array class aims to wrap array types
    from the Stallone library for easy mathematical operations.
    
    Currently it copies the memory, because the Python Java wrapper for arrays
    JArray<T> does not suggerate continuous memory layout, which is needed for
    direct wrapping.
    """
    # TODO: not yet released jpype returns numpy arrays, check for availability.
    # if first argument is of type IIntArray or IDoubleArray
    if not isinstance(stArray, (stallone.api.ints.IIntArray,
                                stallone.api.doubles.IDoubleArray)):
        raise TypeError('can only convert pystallone IDouble- or IIntArrays')
    
    # TODO: support sparse
    # isSparse = d_arr.isSparse()
    
    # if jpype was built against numpy, we directly obtain a numpy array with correct shape here.
    sequence = stArray.getArray()[:]
    
    if type(sequence) is type(_np.ndarray):
        return sequence
    
    # construct an ndarray using a slice of sequence
    dtype = None

    if type(stArray) == stallone.api.doubles.IDoubleArray:
        dtype = _np.float64
    elif type(stArray) == stallone.api.ints.IIntArray:
        dtype = _np.int32

    rows = stArray.rows()
    cols = stArray.columns()
    order = stArray.order()
    
    if cols > 1:
        shape = (rows, cols)
    else:
        shape = (rows,)
    
    if order < 2:
        np_array = _np.array(sequence, dtype=dtype)
    elif order == 2:
        np_array = _np.array(sequence, dtype=dtype)
    else:
        raise NotImplementedError('only 1- and 2-d arrays supported.')
    
    return np_array.reshape(shape)

# FIXME: all functions below assume, that 1d/2d arrays/lists have at least one element, which will raise in case of empty ones.
def list1d_to_java_array(a):
    """
    Converts python list of primitive int or double to java array
    """
    if type(a) is list:
        if type(a[0]) is int:
            return JArray(JInt)(a)
        elif type(a[0]) is float:
            return JArray(JDouble)(a)
        elif type(a[0]) is str:
            return JArray(JString)(a)
        else:
            return JArray(JObject)(a)
    else:
        raise TypeError("Not a list: " + str(a))

def list_to_java_list(a):
    """
    Converts python list of primitive int or double to java array
    """
    if type(a) is list:
        jlist = java.util.ArrayList(len(a))
        for el in a:
            jlist.add(el)
        return jlist
    else:
        raise TypeError("Not a list: " + str(a))


def list2d_to_java_array(a):
    """
    Converts python list of primitive int or double to java array
    """
    if type(a) is list:
        if type(a[0]) is list:
            if type(a[0][0]) is int:
                return JArray(JInt,2)(a)
            elif type(a[0][0]) is float:
                return JArray(JDouble,2)(a)
            elif type(a[0][0]) is str:
                return JArray(JString,2)(a)
            else:
                return JArray(JObject,2)(a)
        else:
            raise TypeError("Not a list: " + str(a[0]))
    else:
        raise TypeError("Not a list: " + str(a))


def list_to_jarray(a):
    """
    Converts 1d or 2d python list of primitive int or double to
    java array or nested array
    """
    if type(a) is list:
        if type(a[0]) is list:
            return list2d_to_java_array(a)
        else:
            return list1d_to_java_array(a)


def jarray(a):
    """
    Converts array-like (python list or ndarray) to java array
    """
    if type(a) is list:
        return list_to_jarray(a)
    elif isinstance(a, _np.ndarray):
        return list_to_jarray(a.tolist())
    else:
        raise TypeError("Type '%s' is not supported for conversion to java array" % type(a))

