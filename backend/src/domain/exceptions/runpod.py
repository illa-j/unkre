class RunPodError(RuntimeError):
    pass


class RunPodNotConfiguredError(RunPodError):
    pass


class RunPodRequestError(RunPodError):
    pass


class RunPodJobNotFoundError(RunPodRequestError):
    pass


class InvalidRunPodResponseError(RunPodError):
    pass
