# Copyright (c) 2012, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

import cherrypy
import routes
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.api import users

import handlers
import models
from models.package import Package
from models.package_version import PackageVersion

class PackageVersions(object):
    """The handler for packages/*/versions/*.

    This handler is in charge of individual versions of packages.
    """

    def index(self, package_id):
        """Retrieve a list of all versions for a given package."""
        package = handlers.request().package
        return handlers.render(
            "packages/versions/index", package=package,
            versions=package.version_set.order('-sort_order').run())

    def new(self, package_id):
        """Retrieve the page for uploading a package version.

        If the user isn't logged in, this presents a login screen. If they are
        logged in but don't own the package, this redirects to the page for the
        package.
        """
        user = users.get_current_user()
        package = handlers.request().package
        if not user:
            raise cherrypy.HTTPRedirect(
                users.create_login_url(cherrypy.url()))
        elif not package.owner == user:
            handlers.flash("You don't down package '%s'" % package.name)
            raise cherrypy.HTTPRedirect('/packages/%s' % package.name)

        return handlers.render("packages/versions/new",
                               action=handlers.request().url(action='create'),
                               package=package)

    @handlers.handle_validation_errors
    def create(self, package_id, file):
        """Create a package version.

        If the user doesn't own the package, this will return a 403 error. If
        the package already has a version with this number, or if the version is
        invalid, this will redirect to the new version form.
        """

        package = handlers.request().package
        if not package.owner == users.get_current_user():
            handlers.http_error(
                403, "You don't own package '%s'" % package.name)

        if not file.file:
            handlers.flash('No package uploaded.')
            raise cherrypy.HTTPRedirect(failure_url)

        version = PackageVersion.new(
            package = package,
            contents_file = file.file)

        failure_url = '/packages/%s/versions/new' % package.name
        if package.has_version(version.version):
            handlers.flash('Package "%s" already has version "%s".' %
                           (package.name, version.version))
            raise cherrypy.HTTPRedirect(failure_url)

        if self._should_update_latest_version(package.latest_version, version):
            package.latest_version = version

        with models.transaction():
            package.put()
            version.put()

        deferred.defer(self._compute_version_order, package)

        handlers.flash('%s %s created successfully.' %
                       (package.name, version.version))
        raise cherrypy.HTTPRedirect('/packages/%s' % package.name)

    def _compute_version_order(self, package):
        """Compute the sort order for all versions of a given package."""
        versions = list(package.version_set.run())
        versions.sort(key=lambda version: version.version)
        for i, version in enumerate(versions):
            version.sort_order = i
        with models.transaction():
            for version in versions: version.put()

    def _should_update_latest_version(self, old, new):
        if old is None: return True
        was_prerelease = old.version.is_prerelease
        is_prerelease = new.version.is_prerelease
        if was_prerelease and not is_prerelease: return True
        if is_prerelease and not was_prerelease: return False
        return old.version < new.version

    def show(self, package_id, id, format):
        """Retrieve the page describing a package version.

        Depending on the format, this could be a user-readable webpage (.html),
        a machine-readable YAML document (.yaml), or a download of the actual
        package blob (.tar.gz).
        """

        # The built-in format parsing has trouble with versions since they
        # contain periods, so we have to undo it and apply our own.
        id = '%s.%s' % (id, format)
        if id.endswith('.tar.gz'):
            id = id[0:-len('.tar.gz')]
            version = handlers.request().package_version(id)
            cherrypy.response.headers['Content-Type'] = \
                'application/octet-stream'
            cherrypy.response.headers['Content-Disposition'] = \
                'attachment; filename=%s-%s.tar.gz' % (package_id, id)
            return version.contents
        elif id.endswith('.yaml'):
            id = id[0:-len('.yaml')]
            version = handlers.request().package_version(id)
            cherrypy.response.headers['Content-Type'] = 'text/yaml'
            return version.pubspec.to_yaml()
        else:
            handlers.http_error(404)
