from pybuilder.core import use_plugin, init

__author__ = 'cody'

use_plugin("pypi:pybuilder_smart_copy_resources")
# use_plugin("source_distribution")
# use_plugin("exec")


@init
def initialize(project):
    project.version = "2.2.0"
    project.name = "servers"
    project.set_property("smart_copy_resources_basedir", ".")
    project.set_property("smart_copy_resources", {
        "aacme.py": "./release"
        # "all/files/here/*": "./other/files",
        # "${name}-additional-files/*": "./additional-files",
    })
    #
    # project.set_property("dir_source_main_python", ".")
    # project.set_property("source_dist_ignore_patterns", ["*.pyc",
    #                                                      ".git*",
    #                                                      "*.zip",
    #                                                      "docs",
    #                                                      "env*",
    #                                                      "portfolio",
    #                                                      "build.py",
    #                                                      "requirements.txt",
    #                                                      ".idea"])
    # project.set_property("dir_source_dist", "$dir_target/{0}".format(project.version))
    # project.set_property("publish_command", "zip -jFSr {dist}/servers-{version}.zip {dist}/{version}".format(version=project.version, dist=project.get_property("dir_target")))
    # project.set_property("publish_propagate_stdout", True)
    # project.set_property("publish_propagate_stderr", True)

# default_task = ["build_source_distribution", "publish"]
default_task = ["smart_copy_resources"]
