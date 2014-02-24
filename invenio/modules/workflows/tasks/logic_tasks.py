def foreach(get_list_function=None, savename=None, cache_data=False, order="ASC"):
    if order not in ["ASC", "DSC"]:
        order = "ASC"

    def _foreach(obj, eng):

        step = str(eng.getCurrTaskId())
        try:
            if "Iterators" not in eng.extra_data:
                eng.extra_data["Iterators"] = {}
        except KeyError:
            eng.extra_data["Iterators"] = {}

        if not step in eng.extra_data["Iterators"]:
            eng.extra_data["Iterators"][step] = {}
            if cache_data:
                eng.extra_data["Iterators"][step]["cache"] = get_list_function(obj, eng)
                my_list_to_process = eng.extra_data["Iterators"][step]["cache"]
            if order == "ASC":
                eng.extra_data["Iterators"][step].update({"value": 0})
            elif order == "DSC":
                eng.extra_data["Iterators"][step].update({"value": len(my_list_to_process) - 1})
            eng.extra_data["Iterators"][step]["previous_data"] = obj.data

        if callable(get_list_function):
            if cache_data:
                my_list_to_process = eng.extra_data["Iterators"][step]["cache"]
            else:
                my_list_to_process = get_list_function(obj, eng)
        elif isinstance(get_list_function, list):
            my_list_to_process = get_list_function
        else:
            my_list_to_process = []

        if order == "ASC" and eng.extra_data["Iterators"][step]["value"] < len(my_list_to_process):
            obj.data = my_list_to_process[eng.extra_data["Iterators"][step]["value"]]
            if savename is not None:
                obj.extra_data[savename] = obj.data
            eng.extra_data["Iterators"][step]["value"] += 1
        elif order == "DSC" and eng.extra_data["Iterators"][step]["value"] > -1:
            obj.data = my_list_to_process[eng.extra_data["Iterators"][step]["value"]]
            if savename is not None:
                obj.extra_data[savename] = obj.data
            eng.extra_data["Iterators"][step]["value"] -= 1
        else:
            obj.data = eng.extra_data["Iterators"][step]["previous_data"]
            del eng.extra_data["Iterators"][step]
            coordonatex = len(eng.getCurrTaskId()) - 1
            coordonatey = eng.getCurrTaskId()[coordonatex]
            new_vector = eng.getCurrTaskId()
            new_vector[coordonatex] = coordonatey + 2
            eng.setPosition(eng.getCurrObjId(), new_vector)

    return _foreach


def simple_for(inita, enda, incrementa, variable_name=None):
    def _simple_for(obj, eng):

        init = inita
        end = enda
        increment = incrementa
        while callable(init):
            init = init(obj, eng)
        while callable(end):
            end = end(obj, eng)
        while callable(increment):
            increment = increment(obj, eng)

        finish = False
        step = str(eng.getCurrTaskId())
        try:
            if "Iterators" not in eng.extra_data:
                eng.extra_data["Iterators"] = {}
        except KeyError:
            eng.extra_data["Iterators"] = {}

        if step not in eng.extra_data["Iterators"]:
            eng.extra_data["Iterators"][step] = {}
            eng.extra_data["Iterators"][step].update({"value": init})

        if (increment > 0 and eng.extra_data["Iterators"][step]["value"] > end) or \
                (increment < 0 and eng.extra_data["Iterators"][step]["value"] < end):
            finish = True
        if not finish:
            if variable_name is not None:
                eng.extra_data["Iterators"][variable_name] = eng.extra_data["Iterators"][step]["value"]
            eng.extra_data["Iterators"][step]["value"] += increment
        else:
            del eng.extra_data["Iterators"][step]
            coordonatex = len(eng.getCurrTaskId()) - 1
            coordonatey = eng.getCurrTaskId()[coordonatex]
            new_vector = eng.getCurrTaskId()
            new_vector[coordonatex] = coordonatey + 2
            eng.setPosition(eng.getCurrObjId(), new_vector)

    return _simple_for


def end_for(obj, eng):
    coordonatex = len(eng.getCurrTaskId()) - 1
    coordonatey = eng.getCurrTaskId()[coordonatex]
    new_vector = eng.getCurrTaskId()
    new_vector[coordonatex] = coordonatey - 3
    eng.setPosition(eng.getCurrObjId(), new_vector)


def get_obj_data(obj, eng):
    eng.log.info("last task name: get_obj_data")
    return obj.data


def execute_if(fun, *args):
    def _execute_if(obj, eng):
        for rule in args:
            res = rule(obj, eng)
            if not res:
                eng.jumpCallForward(1)
        fun(obj, eng)

    return _execute_if


def workflow_if(cond, neg=False):
    def _workflow_if(obj, eng):
        conda = cond
        while callable(conda):
            conda = conda(obj, eng)
        if "state" not in eng.extra_data:
            eng.extra_data["state"] = {}
        step = str(eng.getCurrTaskId())

        if neg:
            conda = not conda
        if step not in eng.extra_data["state"]:
            eng.extra_data["state"].update({step: conda})
        if conda:
            eng.jumpCallForward(1)
        else:
            coordonatex = len(eng.getCurrTaskId()) - 1
            coordonatey = eng.getCurrTaskId()[coordonatex]
            new_vector = eng.getCurrTaskId()
            new_vector[coordonatex] = coordonatey + 1
            eng.setPosition(eng.getCurrObjId(), new_vector)

    return _workflow_if


def workflow_else(obj, eng):
    coordonatex = len(eng.getCurrTaskId()) - 1
    coordonatey = eng.getCurrTaskId()[coordonatex]
    new_vector = eng.getCurrTaskId()[:]
    new_vector[coordonatex] = coordonatey - 2
    if not eng.extra_data["state"][str(new_vector)]:
        eng.jumpCallForward(1)
    else:
        coordonatex = len(eng.getCurrTaskId()) - 1
        coordonatey = eng.getCurrTaskId()[coordonatex]
        new_vector = eng.getCurrTaskId()
        new_vector[coordonatex] = coordonatey + 1
        eng.setPosition(eng.getCurrObjId(), new_vector)