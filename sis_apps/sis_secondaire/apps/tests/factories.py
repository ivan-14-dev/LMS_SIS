"""Factories pour les tests SIS Secondaire."""
import factory
from django.utils import timezone
from faker import Faker

fake = Faker('fr_FR')


class EtablissementFactory(factory.django.DjangoModelFactory):
    """Factory pour Etablissement."""
    class Meta:
        model = 'etablissement.Etablissement'
        django_get_or_create = ('code',)
    
    nom = factory.LazyAttribute(lambda _: f"Lycée {fake.last_name()}")
    code = factory.Sequence(lambda n: f"ETB{n:05d}")
    adresse = factory.LazyAttribute(lambda _: fake.address())
    telephone = factory.LazyAttribute(lambda _: fake.phone_number())
    email = factory.LazyAttribute(lambda _: fake.company_email())
    type_etablissement = 'secondaire'
    actif = True


class AnneeScolaireFactory(factory.django.DjangoModelFactory):
    """Factory pour AnneeScolaire."""
    class Meta:
        model = 'etablissement.AnneeScolaire'
        django_get_or_create = ('libelle',)
    
    libelle = factory.Sequence(lambda n: f"20{24+n//2}-20{25+n//2}")
    date_debut = factory.LazyFunction(timezone.now)
    date_fin = factory.LazyAttribute(lambda o: o.date_debut + timezone.timedelta(days=300))
    en_cours = True


class NiveauFactory(factory.django.DjangoModelFactory):
    """Factory pour Niveau."""
    class Meta:
        model = 'classes.Niveau'
        django_get_or_create = ('code',)
    
    libelle = factory.Iterator(['Seconde', 'Première', 'Terminale'])
    code = factory.Sequence(lambda n: f"NIV{n}")


class FiliereFactory(factory.django.DjangoModelFactory):
    """Factory pour Filiere."""
    class Meta:
        model = 'classes.Filiere'
    
    libelle = factory.Iterator(['Scientifique', 'Littéraire', 'Économique'])
    code = factory.Sequence(lambda n: f"FIL{n}")


class ClasseFactory(factory.django.DjangoModelFactory):
    """Factory pour Classe."""
    class Meta:
        model = 'classes.Classe'
    
    libelle = factory.LazyAttribute(lambda o: f"{o.niveau.libelle} {o.filiere.code}")
    niveau = factory.SubFactory(NiveauFactory)
    filiere = factory.SubFactory(FiliereFactory)
    annee_scolaire = factory.SubFactory(AnneeScolaireFactory)


class MatiereFactory(factory.django.DjangoModelFactory):
    """Factory pour Matiere."""
    class Meta:
        model = 'classes.Matiere'
        django_get_or_create = ('code',)
    
    libelle = factory.Iterator(['Mathématiques', 'Français', 'Anglais', 'Physique-Chimie'])
    code = factory.Sequence(lambda n: f"MAT{n:03d}")
    coefficient = 3


class UtilisateurFactory(factory.django.DjangoModelFactory):
    """Factory pour Utilisateur."""
    class Meta:
        model = 'utilisateurs.Utilisateur'
        django_get_or_create = ('username',)
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    first_name = factory.LazyAttribute(lambda _: fake.first_name())
    last_name = factory.LazyAttribute(lambda _: fake.last_name())
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    role = 'etudiant'
    is_active = True


class PersonnelFactory(factory.django.DjangoModelFactory):
    """Factory pour Personnel (enseignant)."""
    class Meta:
        model = 'enseignants.Personnel'
    
    utilisateur = factory.SubFactory(UtilisateurFactory, role='enseignant')
    matricule = factory.Sequence(lambda n: f"ENS{n:05d}")
    fonction = 'enseignant'


class EleveFactory(factory.django.DjangoModelFactory):
    """Factory pour Eleve."""
    class Meta:
        model = 'eleves.Eleve'
    
    utilisateur = factory.SubFactory(UtilisateurFactory, role='etudiant')
    matricule = factory.Sequence(lambda n: f"ELV{n:06d}")
    date_naissance = factory.LazyFunction(lambda: fake.date_of_birth(minimum_age=14, maximum_age=20))
    sexe = factory.Iterator(['M', 'F'])
    classe = factory.SubFactory(ClasseFactory)


# =========================================================================
# FACTORIES INTEGRATION
# =========================================================================

class EdxUserMappingFactory(factory.django.DjangoModelFactory):
    """Factory pour EdxUserMapping."""
    class Meta:
        model = 'integration.EdxUserMapping'
    
    user_sis = factory.SubFactory(UtilisateurFactory)
    username_edx = factory.LazyAttribute(lambda o: f"sis-s-{o.user_sis.id}")
    user_id_edx = factory.Sequence(lambda n: 10000 + n)
    date_sync = factory.LazyFunction(timezone.now)
    actif = True


class EdxCourseMappingFactory(factory.django.DjangoModelFactory):
    """Factory pour EdxCourseMapping."""
    class Meta:
        model = 'integration.EdxCourseMapping'
    
    matiere = factory.SubFactory(MatiereFactory)
    classe = factory.SubFactory(ClasseFactory)
    course_id = factory.LazyAttribute(
        lambda o: f"course-v1:SIS-S+{o.matiere.code}+{o.classe.annee_scolaire.libelle[:4]}"
    )
    course_name = factory.LazyAttribute(lambda o: f"{o.matiere.libelle} - {o.classe.libelle}")
    actif = True


class EdxEnrollmentFactory(factory.django.DjangoModelFactory):
    """Factory pour EdxEnrollment."""
    class Meta:
        model = 'integration.EdxEnrollment'
    
    eleve = factory.SubFactory(EleveFactory)
    course = factory.SubFactory(EdxCourseMappingFactory)
    enrollment_id = factory.Sequence(lambda n: 50000 + n)
    is_active = True
    progression = 0.0


class EdxGradeLogFactory(factory.django.DjangoModelFactory):
    """Factory pour EdxGradeLog."""
    class Meta:
        model = 'integration.EdxGradeLog'
    
    enrollment = factory.SubFactory(EdxEnrollmentFactory)
    subsection_id = factory.Sequence(lambda n: f"subsection-{n}")
    score = factory.LazyFunction(lambda: fake.pydecimal(min_value=0, max_value=20, right_digits=2))
    max_score = 20
    completion = factory.LazyFunction(lambda: fake.pydecimal(min_value=0, max_value=100, right_digits=2))
    timestamp_lms = factory.LazyFunction(timezone.now)
    imported_to_sis = False


class OutboxEventFactory(factory.django.DjangoModelFactory):
    """Factory pour OutboxEvent."""
    class Meta:
        model = 'integration.OutboxEvent'
    
    event_type = factory.Iterator(['user.created', 'user.updated', 'enrollment.created', 'grade.updated'])
    aggregate_type = factory.Iterator(['user', 'enrollment', 'grade'])
    aggregate_id = factory.Sequence(lambda n: str(n))
    payload = factory.LazyFunction(lambda: {'test': True})
    statut = 'pending'
    nb_tentatives = 0
