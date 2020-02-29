import typing

import torch

from . import convolution


class Conv2dPixelShuffle(torch.nn.Module):
    """Two dimensional convolution with ICNR initialization followed by PixelShuffle.

    `kernel_size` got a default value of `3`, `upscaling`

    Parameters
    ----------
    in_channels : int
        Number of channels in the input image
    out_channels : int
        Number of channels produced after PixelShuffle
    upscale_factor : int
        Factor to increase spatial resolution by. Default: `2`
    kernel_size : int or tuple, optional
        Size of the convolving kernel. Default: `3`
    stride : int or tuple, optional
        Stride of the convolution. Default: 1
    padding: int or tuple, optional
        Zero-padding added to both sides of the input. Default: 0
    padding_mode: string, optional
        Accepted values `zeros` and `circular` Default: `zeros`
    dilation: int or tuple, optional
        Spacing between kernel elements. Default: 1
    groups: int, optional
        Number of blocked connections from input channels to output channels. Default: 1
    bias: bool, optional
        If ``True``, adds a learnable bias to the output. Default: ``True``
    initializer: typing.Callable[[torch.Tensor,], torch.Tensor]
        Initializer for ICNR initialization, can be a function from `torch.nn.init`.
        Gets and returns tensor after initialization

    """

    def __init__(
        self,
        in_channels,
        out_channels,
        upscale_factor: int = 2,
        kernel_size: int = 3,
        stride: int = 1,
        padding: typing.Union[int, str] = "same",  # Fix and use same padding
        dilation: int = 1,
        groups: int = 1,
        bias: bool = True,
        padding_mode: str = "zeros",
        initializer: typing.Callable[
            [torch.Tensor,], torch.Tensor
        ] = torch.nn.init.kaiming_normal_,
    ):
        super().__init__()
        self.convolution = convolution.Conv(
            in_channels,
            out_channels * upscale_factor * upscale_factor,
            kernel_size,
            stride,
            padding,
            dilation,
            groups,
            bias,
            padding_mode,
        )

        self.upsample = torch.nn.PixelShuffle(upscale_factor)
        self.initializer = initializer

    def post_build(self):
        self.icnr_initialization(self.convolution.weight.data)

    def icnr_initialization(self, tensor):
        """ICNR initializer for checkerboard artifact free sub pixel convolution.

        Originally presented in https://arxiv.org/abs/1707.02937.
        Initializes convolutional layer prior to `torch.nn.PixelShuffle`.
        Weights are initialized according to `initializer` passed to to `__init__`.

        Parameters
        ----------
        tensor: torch.Tensor
                Tensor to be initialized using ICNR init.

        Returns
        -------
        torch.Tensor
                Tensor initialized using ICNR.

        """

        if self.upsample.upscale_factor == 1:
            return self.initializer(tensor)

        new_shape = [int(tensor.shape[0] / (self.upsample.upscale_factor ** 2))] + list(
            tensor.shape[1:]
        )

        subkernel = self.initializer(torch.zeros(new_shape)).transpose(0, 1)

        kernel = subkernel.reshape(subkernel.shape[0], subkernel.shape[1], -1).repeat(
            1, 1, self.upsample.upscale_factor ** 2
        )

        return kernel.reshape([-1, tensor.shape[0]] + list(tensor.shape[2:])).transpose(
            0, 1
        )

    def forward(self, inputs):
        return self.upsample(self.convolution(inputs))
