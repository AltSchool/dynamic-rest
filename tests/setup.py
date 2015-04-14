from collections import namedtuple
from tests.models import *


def create_fixture():
  # 4 users sharing 2 groups, 4 permissions, and 3 locations
  # each group has 1 permission
  # 2 of the users share the same location
  # 2 of the users have their own locations

  types = ['users', 'groups', 'locations', 'permissions']
  Fixture = namedtuple('Fixture', types)

  fixture = Fixture(users=[], groups=[], locations=[], permissions=[])

  for i in range(0, 4):
    fixture.users.append(User.objects.create(name=str(i), last_name=str(i)))

  for i in range(0, 4):
    fixture.permissions.append(Permission.objects.create(name=str(i), code=i))

  for i in range(0, 2):
    fixture.groups.append(Group.objects.create(name=str(i)))

  for i in range(0, 3):
    fixture.locations.append(Location.objects.create(name=str(i)))
  fixture.locations[0].blob = 'here'
  fixture.locations[0].save()

  fixture.users[0].location = fixture.locations[0]
  fixture.users[0].save()
  fixture.users[0].groups.add(fixture.groups[0])
  fixture.users[0].groups.add(fixture.groups[1])
  fixture.users[0].permissions.add(fixture.permissions[0])
  fixture.users[0].permissions.add(fixture.permissions[1])

  fixture.users[1].location = fixture.locations[0]
  fixture.users[1].save()
  fixture.users[1].groups.add(fixture.groups[0])
  fixture.users[1].groups.add(fixture.groups[1])
  fixture.users[1].permissions.add(fixture.permissions[2])
  fixture.users[1].permissions.add(fixture.permissions[3])

  fixture.users[2].location = fixture.locations[1]
  fixture.users[2].save()
  fixture.users[2].groups.add(fixture.groups[0])
  fixture.users[2].groups.add(fixture.groups[1])
  fixture.users[2].permissions.add(fixture.permissions[0])
  fixture.users[2].permissions.add(fixture.permissions[3])

  fixture.users[3].location = fixture.locations[2]
  fixture.users[3].save()
  fixture.users[3].groups.add(fixture.groups[0])
  fixture.users[3].groups.add(fixture.groups[1])
  fixture.users[3].permissions.add(fixture.permissions[1])
  fixture.users[3].permissions.add(fixture.permissions[2])

  fixture.groups[0].permissions.add(fixture.permissions[0])
  fixture.groups[1].permissions.add(fixture.permissions[1])

  return fixture
