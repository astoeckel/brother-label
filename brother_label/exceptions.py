class BrotherQLError(Exception):
    pass


class BrotherQLUnknownId(BrotherQLError):
    pass


class BrotherQLUnsupportedCmd(BrotherQLError):
    pass


class BrotherQLUnknownModel(BrotherQLError):
    pass


class BrotherQLRasterError(BrotherQLError):
    pass
