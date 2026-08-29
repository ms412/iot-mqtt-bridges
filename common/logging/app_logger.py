
import copy
import logging
import logging.config

CONSOLE_LOGGER = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "stdformatter": {"format": "%(asctime)s %(levelname)-6s  %(funcName)s() L%(lineno)-4d %(message)s call_trace=%(pathname)s L%(lineno)-4d"},
        "simple": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "stdhandler": {
            "class": "logging.StreamHandler",
            "formatter": "stdformatter",
            'stream': 'ext://sys.stdout'
        },
        "console":{
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "file":{
            "class": "logging.handlers.RotatingFileHandler",
            "level": "CRITICAL",
            "formatter": "simple",
            "filename": "logfile.log",
            "maxBytes": 10485760,
            "backupCount": 40,
            "encoding": "iso-8859-1"
        },
        "syslog":{
            "class": "logging.handlers.SysLogHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "address": ('localhost', 514)
        }
    },
    "loggers" : {
        "root": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True
            }
        }
}

# LOGMODE value that maps to the stdout console handler.
_CONSOLE_MODES = ('CONSOLE',)


class AppLogger:
    """Factory that configures the logging framework and returns a logger."""

    def setup(self, name: str, loggingmode: str, level: str = "DEBUG", **kwargs) -> logging.Logger:
        """Configure logging and return a logger for ``name``.

        Args:
            name: Logger name to return (e.g. the application name).
            loggingmode: One of CONSOLE, FILE, or SYSLOG (case-insensitive).
                CONSOLE logs to stdout.
            level: Log level for the selected handler and the root logger.
            **kwargs: FILE mode accepts ``filename``; SYSLOG accepts ``address``
                and ``port``.

        Returns:
            The configured ``logging.Logger`` instance.
        """
        # Deep-copy so repeated setup() calls do not accumulate mutations on the
        # shared template dict.
        _config = copy.deepcopy(CONSOLE_LOGGER)
        _mode = str(loggingmode).upper()

        if _mode in _CONSOLE_MODES:
            _config['handlers']['console']['level'] = level
            _config['loggers']['root']['handlers'] = ['console']
        elif _mode == 'SYSLOG':
            _config['handlers']['syslog']['level'] = level
            _config['handlers']['syslog']['address'] = (
                kwargs.get('address', 'localhost'),
                kwargs.get('port', 514),
            )
            _config['loggers']['root']['handlers'] = ['syslog']
        elif _mode == 'FILE':
            _config['handlers']['file']['level'] = level
            _config['handlers']['file']['filename'] = kwargs.get('filename', 'logfile.log')
            _config['loggers']['root']['handlers'] = ['file']
        else:
            # Unknown mode: fall back to console so logging is never silently lost.
            _config['handlers']['console']['level'] = level
            _config['loggers']['root']['handlers'] = ['console']

        # Apply the level to the root logger too so dotted child loggers
        # (e.g. modbus2mqtt.modbus_reader.ModbusReader) emit at the same level.
        _config['loggers']['root']['level'] = level

        logging.config.dictConfig(_config)
        return logging.getLogger(name)


if __name__ == '__main__':
    log = AppLogger()
    log.setup('TEST', 'SYSLOG', level='DEBUG', address='10.88.77.1', port=514)
