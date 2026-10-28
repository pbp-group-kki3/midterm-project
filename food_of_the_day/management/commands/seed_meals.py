import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from food_of_the_day.models import MealOfTheDay
from food_of_the_day.constants import CURATED_RECIPE_IDS


class Command(BaseCommand):
    help = "Seeds Meal of the Day entries across upcoming dates from our verified sustainable recipe pool."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Number of days to schedule ahead (default: 365 days / 1 full year).'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear upcoming scheduled meals from today onward before seeding.'
        )

    def handle(self, *args, **options):
        days = options['days']
        clear_first = options['clear']
        today = timezone.localdate()

        if clear_first:
            deleted_count, _ = MealOfTheDay.objects.filter(date__gte=today).delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing meal(s) from {today} onward."))

        num_recipes = len(CURATED_RECIPE_IDS)
        created_count = 0
        existing_count = 0

        for i in range(days):
            target_date = today + datetime.timedelta(days=i)
            # Cycle sequentially through the 100 curated recipes
            recipe_id = CURATED_RECIPE_IDS[i % num_recipes]

            _, created = MealOfTheDay.objects.get_or_create(
                date=target_date,
                defaults={'recipe_id': recipe_id}
            )

            if created:
                created_count += 1
            else:
                existing_count += 1

        end_date = today + datetime.timedelta(days=days - 1)
        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded meals! Scheduled {created_count} new meal(s) across {days} days "
            f"({today.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}) "
            f"using our {num_recipes}-recipe sustainable pool."
        ))
        if existing_count > 0:
            self.stdout.write(self.style.NOTICE(
                f"({existing_count} date(s) already had custom admin entries and were safely preserved.)"
            ))
