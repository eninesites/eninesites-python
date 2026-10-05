"""The eninesites REST client: credentials, the config file, the transport and record shaping.

A library package, not a CLI node: it has no ``__main__``. Every noun's ``api`` reaches the
server through ``http.connect`` and nothing else, so authentication, the base URL, the
error envelope and pagination are decided once, here. Standard library only.
"""
