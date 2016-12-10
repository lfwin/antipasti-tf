__author__ = "Nasim Rahaman"

from ..utilities import utils
from .core import Layer
from .. import backend as A
from ..legacy import pykit as py


class ReplicateLayer(Layer):
    """Layer that replicates its inputs a given `num_replicate` number of times."""
    def __init__(self, num_replicate, dimensions=None, input_shape=None, **layer_kwargs):
        # Init superclass
        super(ReplicateLayer, self).__init__(**layer_kwargs)
        # Attach meta
        self.num_replicate = num_replicate
        # Get input_shape signature and run shape inference
        self.input_shape = utils.get_input_shape(dimensions=dimensions, num_inputs=1, known_input_shape=input_shape,
                                                 _string_stamper=self._stamp_string)

    @utils.forward_pass
    def feedforward(self, input=None):
        # Replicate and return
        return [input] * self.num_replicate

    @utils.shape_inference
    def infer_output_shape(self, input_shape=None):
        return [input_shape] * self.num_replicate


class ConcatenateLayer(Layer):
    """Layer that concatenates its inputs along a given axis."""
    def __init__(self, num_inputs=None, axis=-1, dimensions=None, input_shape=None, **layer_kwargs):
        # Init superclass
        super(ConcatenateLayer, self).__init__(**layer_kwargs)

        # Attach meta
        assert axis in [0, 1, 2, 3, 4, -1], self._stamp_string("Supported axis are [0, 1, 2, 3, 4, -1], got {}.".
                                                               format(axis))
        self.axis = axis

        # Get input shape
        self.input_shape = utils.get_input_shape(dimensions=dimensions, num_inputs=num_inputs,
                                                 known_input_shape=input_shape, _string_stamper=self._stamp_string)

    @utils.forward_pass
    def feedforward(self, input=None):
        return A.concatenate(input, axis=self.axis)

    @utils.shape_inference
    def infer_output_shape(self, input_shape=None):
        # Check input shape for consistency
        input_shape_ok = py.islistoflists(input_shape)
        if self.axis == -1:
            input_shape_ok = input_shape_ok and \
                             all([utils.compare_shapes(ishp[:self.axis], input_shape[0][:self.axis])
                                  for ishp in input_shape])
        else:
            input_shape_ok = input_shape_ok and \
                             all([utils.compare_shapes(ishp[:self.axis] + ishp[(self.axis + 1):],
                                                       input_shape[0][:self.axis] + input_shape[0][(self.axis + 1):])
                                  for ishp in input_shape])

        if not input_shape_ok:
            raise ValueError(self._stamp_string("Given input shape {} is not consistent "
                                                "for concatenation along axis = {}. Check "
                                                "if the shapes of the individual inputs "
                                                "are equal in all but the {}-th dimension.".format(input_shape,
                                                                                                   self.axis,
                                                                                                   self.axis)))
        # Compute output shape
        output_shape = input_shape[0][0:self.axis] + \
                       [sum([ishp[self.axis] for ishp in input_shape])
                        if None not in [ishp[self.axis] for ishp in input_shape]
                        else None] + \
                       (input_shape[0][(self.axis + 1):] if self.axis != -1 else [])
        return output_shape


class AddLayer(Layer):
    """Layer that adds its inputs."""
    def __init__(self, num_inputs=None, dimensions=None, input_shape=None, **layer_kwargs):
        # Initialize superclass
        super(AddLayer, self).__init__(**layer_kwargs)
        # Set input shape
        self.input_shape = utils.get_input_shape(dimensions=dimensions, num_inputs=num_inputs,
                                                 known_input_shape=input_shape, _string_stamper=self._stamp_string)
        # Make sure the number of inputs is larger than 1
        if not self.num_inputs > 1:
            raise ValueError(self._stamp_string("AddLayer expects more than one inputs (got 1). "
                                                "If no `input_shape` is given or if `dimensions` "
                                                "is a scalar, please provide `num_inputs`."))

    @utils.shape_inference
    def infer_output_shape(self, input_shape=None):
        # Validate input_shape
        assert py.islistoflists(input_shape), \
            self._stamp_string("AddLayer expects more than 1 inputs, which implies "
                               "that the `input_shape` should be a list of lists.")
        assert len(input_shape) == self.num_inputs, \
            self._stamp_string("AddLayer expects {} inputs, which is not consistent with "
                               "the provided shape signature implying {} inputs.".
                               format(len(input_shape), self.num_inputs))
        assert all([utils.compare_shapes(_input_shape, input_shape[0], soft=True) for _input_shape in input_shape]), \
            self._stamp_string("All inputs to the AddLayer must have the same shape "
                               "(except for None's). The following `input_shape` is "
                               "therefore not compatible: {}.".format(input_shape))
        # Get output shape and return
        output_shape = input_shape[0]
        return output_shape

    @utils.forward_pass
    def feedforward(self, input=None):
        return A.add_n(inputs=input)


class IdentityLayer(Layer):
    """Layer that does nothing to its input."""
    def __init__(self, dimensions=None, input_shape=None, **layer_kwargs):
        super(IdentityLayer, self).__init__(**layer_kwargs)
        self.input_shape = utils.get_input_shape(dimensions=dimensions, num_inputs=1, known_input_shape=input_shape)

    @utils.forward_pass
    def feedforward(self, input=None):
        return input

    @utils.shape_inference
    def infer_output_shape(self, input_shape=None):
        return input_shape


class FunctionLayer(Layer):
    """Layer that applies a given function to its input."""
    def __init__(self, function, shape_inference_function=None, parameters=None,
                 num_inputs=None, dimensions=None, input_shape=None, **layer_kwargs):
        super(FunctionLayer, self).__init__(**layer_kwargs)

        # Make sure the functions are callable
        if not callable(function):
            raise ValueError(self._stamp_string("The argument `function` must be a callable object."))

        if shape_inference_function is not None and not callable(shape_inference_function):
            raise ValueError(self._stamp_string("The argument `shape_inference_function` must be "
                                                "None or a callable object."))

        # Assign attributes
        self.function = function
        self.shape_inference_function = shape_inference_function \
            if shape_inference_function is not None else lambda _input_shape: _input_shape

        self.input_shape = utils.get_input_shape(dimensions=dimensions, known_input_shape=input_shape,
                                                 num_inputs=num_inputs)
        # Register parameters (assumed present in the function closure, i.e. not fed in to the function at
        # feedforward-time)
        for parameter in parameters:
            self.register_parameter(parameter)

    @utils.forward_pass
    def feedforward(self, input=None):
        return self.function(input)

    @utils.shape_inference
    def infer_output_shape(self, input_shape=None):
        return self.shape_inference_function(input_shape)
