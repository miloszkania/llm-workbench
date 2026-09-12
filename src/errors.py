import openrouter.errors

OPENROUTER_ERRORS = {
    # RETRY ERRORS:
    openrouter.errors.RequestTimeoutResponseError: {
        "message": "The provider did not respond in time. "
                   "Try again later or use another model.",
        "retry": True,
        "kind": "temporary",
    },
    openrouter.errors.InternalServerResponseError: {
        "message": "The provider encountered an internal error. "
                   "Try again later.",
        "retry": True,
        "kind": "temporary",
    },
    openrouter.errors.BadGatewayResponseError: {
        "message": "The provider returned an invalid response. "
                   "Try again later.",
        "retry": True,
        "kind": "temporary",
    },
    openrouter.errors.EdgeNetworkTimeoutResponseError: {
        "message": "The provider timed out. "
                   "Try again later.",
        "retry": True,
        "kind": "network",
    },
    openrouter.errors.ProviderOverloadedResponseError: {
        "message": "The provider was overloaded. "
                   "Try again later.",
        "retry": True,
        "kind": "temporary",
    },
    openrouter.errors.TooManyRequestsResponseError: {
        "message": "The OpenRouter rate limit was reached. "
                   "Wait a moment and try again later.",
        "retry": True,
        "kind": "rate_limit",
    },
    openrouter.errors.ServiceUnavailableResponseError: {
        "message": "OpenRouter is temporarily unavailable. "
                   "Try again later.",
        "retry": True,
        "kind": "temporary",
    },
    openrouter.errors.NoResponseError: {
        "message": "No response was received from the provider. "
                   "Check your connection and try again.",
        "retry": True,
        "kind": "network",
    },

    # NON-RETRY ERRORS:
    openrouter.errors.BadRequestResponseError: {
        "message": "The provider rejected the request. "
                   "Check the input data and try again.",
        "retry": False,
        "kind": "request",
    },
    openrouter.errors.ForbiddenResponseError: {
        "message": "The provider denied the request. "
                   "Check the input data and try again.",
        "retry": False,
        "kind": "request",
    },
    openrouter.errors.NotFoundResponseError: {
        "message": "The information you are looking for was not found. "
                   "Check the input filters and try again.",
        "retry": False,
        "kind": "not_found",
    },
    openrouter.errors.UnauthorizedResponseError: {
        "message": "OpenRouter authentication failed. "
                   "Check your API key and try again.",
        "retry": False,
        "kind": "auth",
    },
    openrouter.errors.PayloadTooLargeResponseError: {
        "message": "The request is too large. "
                   "Shorten the input data and try again.",
        "retry": False,
        "kind": "request",
    },
    openrouter.errors.OpenRouterDefaultError: {
        "message": "The provider returned an unexpected server error. "
                   "Try again later.",
        "retry": False,
        "kind": "unexpected",
    },
    openrouter.errors.OpenRouterError: {
        "message": "The provider returned an unexpected server error. "
                   "Try again later.",
        "retry": False,
        "kind": "unexpected",
    },
    openrouter.errors.PaymentRequiredResponseError: {
        "message": "There are not enough credits to complete the request. "
                   "Add credits or use a free model.",
        "retry": False,
        "kind": "credits",
    },
}

class OpenRouterRequestError(Exception):
    def __init__(self, message, kind, original_error):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.original_error = original_error
