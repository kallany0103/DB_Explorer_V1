CDATA_DEBUG_MODE = False

if CDATA_DEBUG_MODE:
  import logging
  LOG_FORMAT = "%(asctime)s\t %(message)s"
  logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)


def class_logger(cls):
  if CDATA_DEBUG_MODE:
    logger = logging.getLogger(cls.__module__ + "." + cls.__name__)
    cls.logger = logger
  return cls


def mtd_logger(func):
  def wrapper(*args, **kwargs):
    if CDATA_DEBUG_MODE:
      try:
        logger = logging.getLogger("cdata")
        func_name = getattr(func, "__qualname__", getattr(func, "__name__", ""))
        log_msg_lst = [f"Invoke function {func_name}("]
        isFirst = True
        for arg in args:
          if isFirst:
            isFirst = False
          else:
            log_msg_lst.append(", ")
          log_msg_lst.append(str(arg))

        for key, val in kwargs.items():
          if isFirst:
            isFirst = False
          else:
            log_msg_lst.append(", ")
          log_msg_lst.append(str(key))
          log_msg_lst.append("=")
          log_msg_lst.append(str(val))

        log_msg_lst.append(")")

        logger.debug("".join(log_msg_lst))
      except Exception as e:
        pass

    ret = func(*args, **kwargs)

    if CDATA_DEBUG_MODE:
      try:
        logger.debug(f"Invoke function {func.__name__} done, return: {ret}")
      except Exception as e:
        pass

    return ret

  return wrapper