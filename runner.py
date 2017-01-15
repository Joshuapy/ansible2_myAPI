#!/usr/bin/env python
# coding:utf8


from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
import ansible.constants as C
from ansible.errors import AnsibleError
from ansible.utils.vars import load_extra_vars
from ansible.utils.vars import load_options_vars

from myinventory import MyInventory

__all__ = ["Runner"]

# free to report host to `known_hosts` file.
C.HOST_KEY_CHECKING = False

# class Options
Options = namedtuple("Options", [
    'connection', 'module_path', 'private_key_file', "remote_user", "timeout",
    'forks', 'become', 'become_method', 'become_user', 'check', "extra_vars",
    ]
)


class ResultCallback(CallbackBase):
    """
    Custom Callback
    """
    def __init__(self):
        self.result_q = dict(contacted={}, dark={})

    def gather_result(self, n, res, mystate):
        res._result.update({"mystate": mystate})
        self.result_q[n].update({res._host.name: res._result})

    def v2_runner_on_ok(self, result):
        if "changed" in result._result and result._result["changed"]:
            self.gather_result("contacted", result, "changed")
        else:
            self.gather_result("contacted", result, "ok")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.gather_result("dark", result, "failed")

    def v2_runner_on_unreachable(self, result):
        self.gather_result("dark", result, "unreachable")

    def v2_runner_on_skipped(self, result):
        self.gather_result("dark", result, "skipped")

    def v2_playbook_on_task_start(self, task, is_conditional):
        taskname = None

        if hasattr(task, "_ds") and task._ds.get("action"):
            action = task._ds.get("action")
            taskname = "[%s]:%s" % (action.get("module"), action.get("args"))

        if taskname is None and "action" in task._attributes:
            taskname = task._attributes["action"]

        if taskname is None:
            args = ", ".join(('%s=%s' % a for a in task.args.items()))
            args = " %s" % args
            taskname = "%s%s" % (task.get_name().strip(), args)

        self.result_q['task'] = {"id": str(task._uuid), "name": taskname}

    def v2_playbook_on_play_start(self, play):
        # self.result_q['operation'] = {"id": str(play._uuid)}
        pass



class Runner(object):
    """
    仿照ansible1.9 的python API,制作的ansible2.0 API的简化版本。
    参数说明:
        inventory:: 仓库对象，可以是列表，逗号间隔的ip字符串,可执行文件. 默认/etc/ansible/hosts
        module_name:: 指定要使用的模块
        module_args:: 模块参数
        forks:: 并发数量, 默认5
        timeout:: 连接等待超时时间，默认10秒
        pattern:: 模式匹配，指定要连接的主机名, 默认all
        remote_user:: 指定连接用户, 默认root
        private_key_files:: 指定私钥文件
    """
    def __init__(
        self,
        hosts=C.DEFAULT_HOST_LIST,
        module_name=C.DEFAULT_MODULE_NAME,    # * command
        module_args=C.DEFAULT_MODULE_ARGS,    # * ''
        forks=C.DEFAULT_FORKS,                # 5
        timeout=C.DEFAULT_TIMEOUT,            # SSH timeout = 10s
        pattern="all",                        # all
        remote_user=C.DEFAULT_REMOTE_USER,    # root
        module_path=None,                     # dirs of custome modules
        connection_type="smart",
        become=None,
        become_method=None,
        become_user=None,
        check=False,
        passwords=None,
        extra_vars = None,
        private_key_file=None
    ):

        # storage & defaults
        self.pattern = pattern
        self.variable_manager = VariableManager()
        self.loader = DataLoader()
        self.module_name = module_name
        self.module_args = module_args
        self.check_module_args()
        self.gather_facts = False
        # self.gather_facts = gather_facts
        self.resultcallback = ResultCallback()
        self.options = Options(
            connection=connection_type,
            timeout=timeout,
            module_path=module_path,
            forks=forks,
            become=become,
            become_method=become_method,
            become_user=become_user,
            check=check,
            remote_user=remote_user,
            extra_vars=extra_vars or [],
            private_key_file=private_key_file,
        )

        self.variable_manager.extra_vars = load_extra_vars(loader=self.loader, options=self.options)
        self.variable_manager.options_vars = load_options_vars(self.options)

        self.passwords = passwords or {}
        self.inventory = MyInventory(host_list=hosts)
        self.variable_manager.set_inventory(self.inventory)

        self.play_source = dict(
            name="Ansible API Play",
            hosts=self.pattern,
            gather_facts='yes' if self.gather_facts else 'no',
            tasks=[dict(action=dict(
                module=self.module_name, args=self.module_args))]
        )

        self.play = Play().load(
            self.play_source, variable_manager=self.variable_manager,
            loader=self.loader)

        self.runner = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
                stdout_callback=self.resultcallback
                # stdout_callback = 'minimal',
        )

        # end __init__()

    def run(self):
        if not self.inventory.list_hosts("all"):
            raise AnsibleError("Inventory is empty.")

        if not self.inventory.list_hosts(self.pattern):
            raise AnsibleError(
                "pattern: %s  dose not match any hosts." % self.pattern)

        try:
            self.runner.run(self.play)
        except Exception as e:
            raise Exception(e)
        else:
            return self.resultcallback.result_q
        finally:
            if self.runner:
                self.runner.cleanup()
            if self.loader:
                self.loader.cleanup_all_tmp_files()


    def check_module_args(self):
        if self.module_name in C.MODULE_REQUIRE_ARGS and not self.module_args:
            err = "No argument passed to '%s' module." % self.module_name
            raise AnsibleError(err)
