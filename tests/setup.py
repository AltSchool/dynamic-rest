from collections import namedtuple

from tests.models import (
    Cat,
    Dog,
    Event,
    Group,
    Horse,
    Location,
    Permission,
    User,
    Zebra
)


def create_fixture():
    # 4 users sharing 2 groups, 4 permissions, and 3 locations
    # each group has 1 permission
    # one location has a cat.
    # 2 of the users share the same location
    # 2 of the users have their own locations
    # Create 4 dogs.

    types = [
        'users', 'groups', 'locations', 'permissions',
        'events', 'cats', 'dogs', 'horses', 'zebras'
    ]
    Fixture = namedtuple('Fixture', types)

    fixture = Fixture(
        users=[], groups=[], locations=[], permissions=[],
        events=[], cats=[], dogs=[], horses=[], zebras=[]
    )

    for i in range(0, 4):
        fixture.users.append(
            User.objects.create(
                name=str(i),
                last_name=str(i)))

    for i in range(0, 4):
        fixture.permissions.append(
            Permission.objects.create(
                name=str(i),
                code=i))

    for i in range(0, 2):
        fixture.groups.append(Group.objects.create(name=str(i)))

    for i in range(0, 3):
        fixture.locations.append(Location.objects.create(name=str(i)))

    for i in range(0, 2):
        fixture.cats.append(Cat.objects.create(
            name=str(i),
            home_id=fixture.locations[i].id,
            backup_home_id=(
                fixture.locations[len(fixture.locations) - 1 - i].id)))

    dogs = [{
        'name': 'Clifford',
        'fur_color': 'red',
        'origin': 'Clifford the big red dog'
    }, {
        'name': 'Air-Bud',
        'fur_color': 'gold',
        'origin': 'Air Bud 4: Seventh Inning Fetch'
    }, {
        'name': 'Spike',
        'fur_color': 'brown',
        'origin': 'Rugrats'
    }, {
        'name': 'Pluto',
        'fur_color': 'brown and white',
        'origin': 'Mickey Mouse'
    }, {
        'name': 'Spike',
        'fur_color': 'light-brown',
        'origin': 'Tom and Jerry'
    }]

    horses = [{
        'name': 'Seabiscuit',
        'origin': 'LA'
    }, {
        'name': 'Secretariat',
        'origin': 'Kentucky'
    }]

    zebras = [{
        'name': 'Ralph',
        'origin': 'new york'
    }, {
        'name': 'Ted',
        'origin': 'africa'
    }]

    events = [{
        'name': 'Event 1',
        'status': 'archived',
        'location': 2
    }, {
        'name': 'Event 2',
        'status': 'current',
        'location': 1
    }, {
        'name': 'Event 3',
        'status': 'current',
        'location': 1
    }, {
        'name': 'Event 4',
        'status': 'archived',
        'location': 2
    }, {
        'name': 'Event 5',
        'status': 'current',
        'location': 2
    }]

    for dog in dogs:
        fixture.dogs.append(Dog.objects.create(
            name=dog.get('name'),
            fur_color=dog.get('fur_color'),
            origin=dog.get('origin')
        ))

    for horse in horses:
        fixture.horses.append(Horse.objects.create(
            name=horse.get('name'),
            origin=horse.get('origin')
        ))

    for zebra in zebras:
        fixture.zebras.append(Zebra.objects.create(
            name=zebra.get('name'),
            origin=zebra.get('origin')
        ))

    for event in events:
        fixture.events.append(Event.objects.create(
            name=event['name'],
            status=event['status'],
            location_id=event['location']
        ))
    fixture.events[1].users.add(fixture.users[0])
    fixture.events[1].users.add(fixture.users[1])
    fixture.events[2].users.add(fixture.users[0])
    fixture.events[3].users.add(fixture.users[0])
    fixture.events[3].users.add(fixture.users[2])
    fixture.events[4].users.add(fixture.users[0])
    fixture.events[4].users.add(fixture.users[1])
    fixture.events[4].users.add(fixture.users[2])

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
