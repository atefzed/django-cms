from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from cms import settings as cms_settings
from cms.tests.base import PageBaseTestCase, URL_CMS_PAGE_ADD, URL_CMS_PAGE,\
    URL_CMS_PAGE_CHANGE
from cms.models import Title, Page


class PermissionModeratorTestCase(PageBaseTestCase):
    """Permissions and moderator together
    
    Fixtures contains 3 users and 1 published page and some other stuff
    
    Users:
        1. `super`: superuser
        2. `master`: user with permissions to all aplications
        3. `slave`: user assigned to page `slave-home` can add/change/delete page
    
    Pages:
        1. `home`:
            - published page
            - master can do anything on its subpages, but not on home!
            
        2. `master`:
            - crated by super
            - subpages:
        
        3.       `slave-home`: 
                    - assigned slave user which can add/change/delete this page and its descendants
                    - `master` user want to moderate this page and all descendants
                    
        4. `pageA`:
            - created by super
            - master can add/change/delete on it and descendants 
    """
    
    # ./run dumpdata --format=yaml --indent=4 -e south -e contenttypes -e reversion > ../cms/tests/fixtures/permission.yaml
    fixtures = ['../cms/tests/fixtures/permission.yaml']
    
    # helpers
    
    def _add_plugin(self, user):
        slave_page = self.slave_page
        
        post_data = {
            'language': 'en',
            'page_id': slave_page.pk,
            'placeholder': 'Right-Column',
            'plugin_type': 'TextPlugin'
        }
        self.login_user(user)
        url = URL_CMS_PAGE + "%d/add-plugin/" % slave_page.pk
        response = self.client.post(url, post_data)
        assert(response.content == "1")
        
    def _create_page(self, parent_page=None, user=None):
        if user:
            # change logged in user
            self.login_user(user)
        
        slave_page = self.slave_page
        page_data = self.get_new_page_data()
        
        page_data.update({
            '_save': 'Save',
        })
        
        # add page
        if parent_page:
            url = URL_CMS_PAGE_ADD + "?target=%d&position=first-child" % parent_page.pk
        else:
            url = URL_CMS_PAGE_ADD
        response = self.client.post(url, page_data)
        self.assertRedirects(response, URL_CMS_PAGE)
        
        # public model shouldn't be available yet, because of the moderation
        self.assertObjectExist(Title.objects, slug=page_data['slug'])
        self.assertObjectDoesNotExist(Title.PublicModel.objects, slug=page_data['slug'])
        
        return self.assertObjectExist(Page.objects, title_set__slug=page_data['slug'])
    
    def _publish_page(self, page, approve=False, user=None, published_check=True):
        if user:
            self.login_user(user)
            
        # publish / approve page by master
        response = self.client.post(URL_CMS_PAGE + "%d/change-status/" % page.pk, {1 :1})
        assert(response.status_code, 200)
        
        if not approve:
            return self._reload(page)
        
        # approve
        page = self._approve_page(page)
        
        if published_check:
            # must have public object now
            assert(page.public)
            # and public object must be published
            assert(page.public.published)
        
        return page
    
    def _approve_page(self, page):
        response = self.client.get(URL_CMS_PAGE + "%d/approve/" % page.pk)
        self.assertRedirects(response, URL_CMS_PAGE)
        # reload page
        return self._reload(page)
    
    def _reload(self, page):
        page = self.assertObjectExist(Page.objects, id=page.pk)
        return page
    
    def _check_published_page_attributes(self, page):
        public_page = page.public
        compare = ['id', 'tree_id', 'rght', 'lft', 'parent_id', 'level']
        # compare ids and tree attributes
        for name in compare:
            assert(getattr(page, name) == getattr(public_page, name))
    
    def _add_page(self, user):
        """Helper for accessing new page creation
        """
        self._login_user(user)
        return self.client.get('/admin/cms/page/add/')
    
    def _copy_page(self, page, target_page):
        from cms.utils.page import get_available_slug
        
        data = {
            'position': 'first-child',
            'target': target_page.pk,
            'site': 1,
            'copy_permissions': 'on',
            'copy_moderation': 'on',
        }
        
        response = self.client.post(URL_CMS_PAGE + "%d/copy-page/" % page.pk, data)
        assert(response.status_code, 200)
        
        title = page.title_set.all()[0]
        
        copied_slug = get_available_slug(title)
        copied_page = self.assertObjectExist(Page.objects, title_set__slug=copied_slug, parent=target_page)
        return copied_page
    
    def assertObjectExist(self, qs, **filter):
        try:
            return qs.get(**filter) 
        except ObjectDoesNotExist:
            pass
        raise self.failureException, "ObjectDoesNotExist raised"
    
    def assertObjectDoesNotExist(self, qs, **filter):
        try:
            qs.get(**filter) 
        except ObjectDoesNotExist:
            return
        raise self.failureException, "ObjectDoesNotExist not raised"
    
    @property
    def home_page(self):
        return Page.objects.get(title_set__slug="home")
    
    @property
    def slave_page(self):
        return Page.objects.get(title_set__slug="slave-home")
    
    @property
    def master_page(self):
        return Page.objects.get(title_set__slug="master")
    
    
    # tests
            
    
    def setUp(self):
        self.user_super = User.objects.get(username="super")
        self.user_master = User.objects.get(username="master")
        self.user_slave = User.objects.get(username="slave")
    
    
    def test_00_configuration(self):
        """Just check if we have right configuration for this test. Problem lies
        in cms_settings!! something like cms_settings.CMS_MODERATOR = True just
        doesn't work!!!
        
        TODO: settings must be changed to be configurable / overridable
        """
        assert(cms_settings.CMS_PERMISSION)
        assert(cms_settings.CMS_MODERATOR)
    
    
    def test_01_super_can_add_page_to_root(self, status_code=200):
        self.login_user(self.user_super)
        response = self.client.get(URL_CMS_PAGE_ADD)
        self.assertEqual(response.status_code, status_code)
    
    
    def test_02_master_can_add_page_to_root(self, status_code=403):
        self.login_user(self.user_master)
        response = self.client.get(URL_CMS_PAGE_ADD)
        self.assertEqual(response.status_code, status_code)
    
        
    def test_03_slave_can_add_page_to_root(self, status_code=403):
        self.login_user(self.user_slave)
        response = self.client.get(URL_CMS_PAGE_ADD)
        self.assertEqual(response.status_code, status_code)
    
    
    def test_04_moderation_on_slave_home(self):
        assert(self.slave_page.get_moderator_queryset().count()==1)
    
    
    def test_05_slave_can_add_page_under_slave_home(self):
        self.login_user(self.user_slave)
        slave_page = self.slave_page
        page_data = self.get_new_page_data()
        
        # reuest moderation
        page_data.update({
            #'moderator_state': Page.MODERATOR_NEED_APPROVEMENT,
            #'moderator_message': "Approve me!",
            '_save': 'Save',
        })
        
        # add page
        url = URL_CMS_PAGE_ADD + "?target=%d&position=first-child" % slave_page.pk
        response = self.client.post(url, page_data)
        self.assertRedirects(response, URL_CMS_PAGE)
        
        # public model shouldn't be available yet, because of the moderation
        self.assertObjectExist(Title.objects, slug=page_data['slug'])
        self.assertObjectDoesNotExist(Title.PublicModel.objects, slug=page_data['slug'])
        
        # page created?
        page = self.assertObjectExist(Page.objects, title_set__slug=page_data['slug'])
        # moderators and approvemnt right?
        assert(page.get_moderator_queryset().count()==1)
        #assert(page.moderator_state == Page.MODERATOR_NEED_APPROVEMENT)
        
        # must not have public object yet
        assert(not page.public)
        
        # publish / approve page by master
        self.login_user(self.user_master)
        
        response = self.client.post(URL_CMS_PAGE + "%d/change-status/" % page.pk, {1 :1})
        assert(response.status_code == 200)
        
        # approve / publish
        page = self._approve_page(page)
        
    
    def test_06_super_can_add_plugin(self):
        self._add_plugin(self.user_super)
    
    
    def test_07_master_can_add_plugin(self):
        self._add_plugin(self.user_master)
    
        
    def test_08_slave_can_add_plugin(self):
        self._add_plugin(self.user_slave)
    
    def test_09_public_model_attributes(self):
        self.login_user(self.user_master)
        
        # create 10 pages
        slugs = []
        for i in range(0, 10):
            page = self._create_page(self.home_page)
            slug = page.title_set.all()[0].slug
            slugs.append(slug)
        
        # approve last 5 pages in reverse order
        self.login_user(self.user_master)
        
        for slug in reversed(slugs[5:]):
            page = self.assertObjectExist(Page.objects, title_set__slug=slug)
            
            public_page = self._publish_page(page, True)
            self._check_published_page_attributes(public_page)
    
    
    def test_10_create_copy_publish(self):
        # create new page to copy
        self.login_user(self.user_master)
        page = self._create_page(self.slave_page)
        
        # copy it under home page...
        copied_page = self._copy_page(page, self.home_page)
        
        page = self._publish_page(copied_page, True)
        self._check_published_page_attributes(page)
    
    
    def test_11_create_publish_copy(self):
        # create new page to copy
        self.login_user(self.user_master)
        page = self._create_page(self.home_page)
        
        page = self._publish_page(page, True)
        
        # copy it under master page...
        copied_page = self._copy_page(page, self.master_page)
        
        self._check_published_page_attributes(page)
        self._check_published_page_attributes(copied_page)
        
        
    def test_12_subtree_needs_approvement(self):
        self.login_user(self.user_master)
        # create page under slave_page
        page = self._create_page(self.home_page)
        assert(not page.public)
        
        # create subpage uner page
        subpage = self._create_page(page)
        assert(not subpage.public)
        
        # publish both of them in reverse order 
        subpage = self._publish_page(subpage, True, published_check=False) 
        
        # subpage should not be published, because parent is not published 
        # yet, should be marked as `publish when parent`
        assert(not subpage.public) 
        
        # pagemoderator state must be set
        assert(subpage.moderator_state == Page.MODERATOR_APPROVED_WAITING_FOR_PARENTS)
        
        # publish page (parent of subage), so subpage must be published also
        page = self._publish_page(page, True)
        assert(page.public)
        
        # reload subpage, it was probably changed
        subpage = self._reload(subpage)
        
        # parent was published, so subpage must be also published..
        assert(subpage.public) 
        
        #check attributes
        self._check_published_page_attributes(page)
        self._check_published_page_attributes(subpage)


    def test_13_subtree_with_super(self):
        self.login_user(self.user_super)
        # create page under root
        page = self._create_page()
        assert(not page.public)
        
        # create subpage under page
        subpage = self._create_page(page)
        assert(not subpage.public)
        
        # publish both of them in reverse order 
        page = self._publish_page(page, True)
        subpage = self._publish_page(subpage, True)
        
        #check attributes
        self._check_published_page_attributes(page) 
        self._check_published_page_attributes(subpage)
        
    def test_14_super_add_page_to_root(self):
        """Create page which is not under moderation in root, and check if 
        some properties are correct.
        """
        self.login_user(self.user_super)
        # create page under root
        page = self._create_page()
        
        # public must not exist
        assert(not page.public)
        
        # moderator_state must be changed
        assert(page.moderator_state == Page.MODERATOR_CHANGED)
    
    def test_15_moderator_flags(self):
        """Add page under slave_home and check its flag
        """
        self.login_user(self.user_slave)
        page = self._create_page(self.slave_page)
        
        # moderator_state must be changed
        assert(page.moderator_state == Page.MODERATOR_CHANGED)
        
        # check publish box
        page = self._publish_page(page, published_check=False)
        
        # page should request approvement now
        assert(page.moderator_state == Page.MODERATOR_NEED_APPROVEMENT)
        
        # approve it by master
        self.login_user(self.user_master)
        
        # approve this page - but it doesn't get published yet, because 
        # slave home is not published
        page = self._approve_page(page)
        
        # public page must not exist because of parent
        assert(not page.public)
        
        # waiting for parents
        assert(page.moderator_state == Page.MODERATOR_APPROVED_WAITING_FOR_PARENTS)
        
        # publish master page
        master = self._publish_page(self.master_page)
        
        # master is approved
        assert(master.moderator_state == Page.MODERATOR_APPROVED)
        
        # reload page
        page = self._reload(page)
        
        # page must be approved also now
        assert(page.moderator_state == Page.MODERATOR_APPROVED)
        
        
        
        
        
        
        