# Copyright (c) Microsoft Corporation.
# SPDX-License-Identifier: Apache-2.0

# DeepSpeed Team

import os
import pkgutil
import importlib

from .abstract_accelerator import DeepSpeedAccelerator
# During setup stage torch may not be installed, pass on no torch will
# allow op builder related API to be executed.
import torch_musa



class MUSA_Accelerator(DeepSpeedAccelerator):

    def __init__(self):
        self._name = 'musa'
        self._communication_backend_name = 'mccl'

    def is_synchronized_device(self):
        return False

    # Device APIs
    def device_name(self, device_index=None):
        if device_index == None:
            return 'musa'
        return 'musa:{}'.format(device_index)

    def device(self, device_index=None):
        return torch_musa.device(device_index)

    def set_device(self, device_index):
        torch_musa.set_device(device_index)

    def current_device(self):
        return torch_musa.current_device()

    def current_device_name(self):
        return 'musa:{}'.format(torch_musa.current_device())

    def device_count(self):
        return torch_musa.device_count()

    def synchronize(self, device_index=None):
        return torch_musa.synchronize(device_index)

    # RNG APIs
    def random(self):
        return torch.random

    def set_rng_state(self, new_state, device_index=None):
        if device_index is None:
            return torch_musa.set_rng_state(new_state)

        return torch_musa.set_rng_state(new_state, device_index)

    def get_rng_state(self, device_index=None):
        if device_index is None:
            return torch_musa.get_rng_state()

        return torch_musa.get_rng_state(device_index)

    def manual_seed(self, seed):
        return torch_musa.manual_seed(seed)

    def manual_seed_all(self, seed):
        return torch_musa.manual_seed_all(seed)

    def initial_seed(self, seed):
        return torch_musa.initial_seed(seed)

    def default_generator(self, device_index):
        return torch_musa.default_generators[device_index]

    # Streams/Events
    @property
    def Stream(self):
        return torch_musa.Stream

    def stream(self, stream):
        return torch_musa.stream(stream)

    def current_stream(self, device_index=None):
        return torch_musa.current_stream(device_index)

    def default_stream(self, device_index=None):
        return torch_musa.default_stream(device_index)

    @property
    def Event(self):
        return torch_musa.Event

    # Memory management
    def empty_cache(self):
        return torch_musa.empty_cache()

    def memory_allocated(self, device_index=None):
        return torch_musa.memory_allocated(device_index)

    def max_memory_allocated(self, device_index=None):
        return torch_musa.max_memory_allocated(device_index)

    def reset_max_memory_allocated(self, device_index=None):
        return torch_musa.reset_max_memory_allocated(device_index)

    def memory_cached(self, device_index=None):
        return torch_musa.memory_cached(device_index)

    def max_memory_cached(self, device_index=None):
        return torch_musa.max_memory_cached(device_index)

    def reset_max_memory_cached(self, device_index=None):
        return torch_musa.reset_max_memory_cached(device_index)

    def memory_stats(self, device_index=None):
        if hasattr(torch_musa, 'memory_stats'):
            return torch_musa.memory_stats(device_index)

    def reset_peak_memory_stats(self, device_index=None):
        if hasattr(torch_musa, 'reset_peak_memory_stats'):
            return torch_musa.reset_peak_memory_stats(device_index)

    def memory_reserved(self, device_index=None):
        if hasattr(torch_musa, 'memory_reserved'):
            return torch_musa.memory_reserved(device_index)

    def max_memory_reserved(self, device_index=None):
        if hasattr(torch_musa, 'max_memory_reserved'):
            return torch_musa.max_memory_reserved(device_index)

    def total_memory(self, device_index=None):
        return torch_musa.get_device_properties(device_index).total_memory

    # Data types
    def is_bf16_supported(self):
        return torch_musa.is_bf16_supported()

    def is_fp16_supported(self):
        major, _ = torch_musa.get_device_capability()
        if major >= 7:
            return True
        else:
            return False

    # Misc
    def amp(self):
        if hasattr(torch_musa, 'amp'):
            return torch_musa.amp
        return None

    def is_available(self):
        return torch_musa.is_available()

    def range_push(self, msg):
        if hasattr(torch_musa.nvtx, 'range_push'):
            return torch_musa.nvtx.range_push(msg)

    def range_pop(self):
        if hasattr(torch_musa.nvtx, 'range_pop'):
            return torch_musa.nvtx.range_pop()

    def lazy_call(self, callback):
        return torch_musa._lazy_call(callback)

    def communication_backend_name(self):
        return self._communication_backend_name

    # Tensor operations

    @property
    def BFloat16Tensor(self):
        return torch_musa.BFloat16Tensor

    @property
    def ByteTensor(self):
        return torch_musa.ByteTensor

    @property
    def DoubleTensor(self):
        return torch_musa.DoubleTensor

    @property
    def FloatTensor(self):
        return torch_musa.FloatTensor

    @property
    def HalfTensor(self):
        return torch_musa.HalfTensor

    @property
    def IntTensor(self):
        return torch_musa.IntTensor

    @property
    def LongTensor(self):
        return torch_musa.LongTensor

    def pin_memory(self, tensor):
        return tensor.pin_memory()

    def on_accelerator(self, tensor):
        device_str = str(tensor.device)
        if device_str.startswith('musa:'):
            return True
        else:
            return False

    def op_builder_dir(self):
        try:
            # is op_builder from deepspeed or a 3p version? this should only succeed if it's deepspeed
            # if successful this also means we're doing a local install and not JIT compile path
            from op_builder import __deepspeed__  # noqa: F401
            return "op_builder"
        except ImportError:
            return "deepspeed.ops.op_builder"

    # dict that holds class name <--> class type mapping i.e.
    # 'AsyncIOBuilder': <class 'op_builder.async_io.AsyncIOBuilder'>
    # this dict will be filled at init stage
    class_dict = None

    def _lazy_init_class_dict(self):
        if self.class_dict != None:
            return
        else:
            self.class_dict = {}
            # begin initialize for create_op_builder()
            # put all valid class name <--> class type mapping into class_dict
            op_builder_dir = self.op_builder_dir()
            op_builder_module = importlib.import_module(op_builder_dir)
            for _, module_name, _ in pkgutil.iter_modules([os.path.dirname(op_builder_module.__file__)]):
                # avoid self references
                if module_name != 'all_ops' and module_name != 'builder' and module_name != 'cpu':
                    module = importlib.import_module("{}.{}".format(op_builder_dir, module_name))
                    for member_name in module.__dir__():
                        if member_name.endswith(
                                'Builder'
                        ) and member_name != "OpBuilder" and member_name != "CUDAOpBuilder" and member_name != "TorchCPUOpBuilder":  # avoid abstract classes
                            if not member_name in self.class_dict:
                                self.class_dict[member_name] = getattr(module, member_name)
            # end initialize for create_op_builder()

    # create an instance of op builder and return, name specified by class_name
    def create_op_builder(self, class_name):
        self._lazy_init_class_dict()
        if class_name in self.class_dict:
            return self.class_dict[class_name]()
        else:
            return None

    # return an op builder class, name specified by class_name
    def get_op_builder(self, class_name):
        self._lazy_init_class_dict()
        if class_name in self.class_dict:
            return self.class_dict[class_name]
        else:
            return None

    def build_extension(self):
        from torch.utils.cpp_extension import BuildExtension
        return BuildExtension
