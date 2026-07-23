"""Factories pour générer des données de test - SIS Supérieur."""
import factory
from factory.django import DjangoModelFactory
from factory import Faker, SubFactory, Sequence, LazyAttribute
from django.utils import timezone

from apps.utilisateurs.models import Utilisateur
from apps.etablissement.models import Universite, AnneeUniversitaire, Semestre, Domain
from apps.structure.models import Faculte, Departement, EcoleDoctorale
from apps.formations.models import Formation, Parcours, MaquetteFormation
from apps.ue_ecue.models import UE, ECUE
from apps.etudiants.models import Etudiant, InscriptionAdministrative, InscriptionPedagogique
from apps.integration.models import EdxUserMapping, EdxCourseMapping, EdxEnrollment, OutboxEvent


# =============================================================================
# ÉTABLISSEMENT
# =============================================================================

class UniversiteFactory(DjangoModelFactory):
    class Meta:
        model = Universite
    
    schema_name = Sequence(lambda n: f'univ_{n}')
    nom = Faker('company', locale='fr_FR')
    type = 'universite_publique'
    sigle = Sequence(lambda n: f'U{n:02d}')
    adresse = Faker('address', locale='fr_FR')
    code_postal = Faker('postcode', locale='fr_FR')
    ville = Faker('city', locale='fr_FR')
    pays = 'France'
    telephone = Faker('phone_number', locale='fr_FR')
    email = Faker('email')
    actif = True


class DomainFactory(DjangoModelFactory):
    class Meta:
        model = Domain
    
    domain = Sequence(lambda n: f'tenant{n}.sis.local')
    tenant = SubFactory(UniversiteFactory)
    is_primary = True


class AnneeUniversitaireFactory(DjangoModelFactory):
    class Meta:
        model = AnneeUniversitaire
    
    universite = SubFactory(UniversiteFactory)
    libelle = Sequence(lambda n: f'202{n}-202{n+1}')
    date_debut = Faker('date_this_year')
    date_fin = LazyAttribute(lambda o: o.date_debut.replace(year=o.date_debut.year + 1))
    en_cours = True
    cloturee = False


class SemestreFactory(DjangoModelFactory):
    class Meta:
        model = Semestre
    
    annee_universitaire = SubFactory(AnneeUniversitaireFactory)
    numero = Sequence(lambda n: (n % 6) + 1)
    type = LazyAttribute(lambda o: 'impair' if o.numero % 2 == 1 else 'pair')
    date_debut = Faker('date_this_year')
    date_fin = Faker('date_this_year')
    cloture = False


# =============================================================================
# UTILISATEURS
# =============================================================================

class UtilisateurFactory(DjangoModelFactory):
    class Meta:
        model = Utilisateur
    
    username = Sequence(lambda n: f'user_{n}')
    email = LazyAttribute(lambda o: f'{o.username}@example.com')
    first_name = Faker('first_name', locale='fr_FR')
    last_name = Faker('last_name', locale='fr_FR')
    role = 'etudiant'
    is_active = True
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop('password', 'testpass123')
        user = super()._create(model_class, *args, **kwargs)
        user.set_password(password)
        user.save()
        return user


class EnseignantFactory(UtilisateurFactory):
    role = 'enseignant'
    numero_enseignant = Sequence(lambda n: f'ENS{n:06d}')


class AdminFactory(UtilisateurFactory):
    role = 'scolarite'
    is_staff = True


# =============================================================================
# STRUCTURE
# =============================================================================

class FaculteFactory(DjangoModelFactory):
    class Meta:
        model = Faculte
    
    universite = SubFactory(UniversiteFactory)
    nom = Faker('catch_phrase', locale='fr_FR')
    code = Sequence(lambda n: f'FAC{n:02d}')
    doyen = SubFactory(UtilisateurFactory, role='doyen')
    actif = True


class DepartementFactory(DjangoModelFactory):
    class Meta:
        model = Departement
    
    faculte = SubFactory(FaculteFactory)
    nom = Faker('job', locale='fr_FR')
    code = Sequence(lambda n: f'DEPT{n:02d}')
    directeur = SubFactory(UtilisateurFactory, role='directeur_dept')


class EcoleDoctoraleFactory(DjangoModelFactory):
    class Meta:
        model = EcoleDoctorale
    
    universite = SubFactory(UniversiteFactory)
    nom = Sequence(lambda n: f'École Doctorale {n}')
    code = Sequence(lambda n: f'ED{n:02d}')


# =============================================================================
# FORMATIONS
# =============================================================================

class FormationFactory(DjangoModelFactory):
    class Meta:
        model = Formation
    
    departement = SubFactory(DepartementFactory)
    nom = Sequence(lambda n: f'Licence Informatique {n}')
    code = Sequence(lambda n: f'LINF{n:02d}')
    type = 'licence'
    niveau = 'L1'
    duree_annees = 3
    nb_semestres = 6
    credits_total = 180
    actif = True


class ParcoursFactory(DjangoModelFactory):
    class Meta:
        model = Parcours
    
    formation = SubFactory(FormationFactory)
    nom = Sequence(lambda n: f'Parcours {n}')
    code = Sequence(lambda n: f'P{n:02d}')


class MaquetteFormationFactory(DjangoModelFactory):
    class Meta:
        model = MaquetteFormation
    
    formation = SubFactory(FormationFactory)
    annee_universitaire = SubFactory(AnneeUniversitaireFactory)
    statut = 'validee'
    structure = {}


# =============================================================================
# UE / ECUE
# =============================================================================

class UEFactory(DjangoModelFactory):
    class Meta:
        model = UE
    
    maquette = SubFactory(MaquetteFormationFactory)
    code = Sequence(lambda n: f'UE{n:03d}')
    nom = Sequence(lambda n: f'Unité d\'Enseignement {n}')
    credits_ects = 6
    type = 'F'
    volume_horaire_cm = 20
    volume_horaire_td = 20
    volume_horaire_tp = 10
    semestre = SubFactory(SemestreFactory)


class ECUEFactory(DjangoModelFactory):
    class Meta:
        model = ECUE
    
    ue = SubFactory(UEFactory)
    code = Sequence(lambda n: f'ECUE{n:03d}')
    nom = Sequence(lambda n: f'Élément {n}')
    credits_ects = 3
    coefficient = 1
    volume_horaire_cm = 10
    volume_horaire_td = 10
    volume_horaire_tp = 5


# =============================================================================
# ÉTUDIANTS
# =============================================================================

class EtudiantFactory(DjangoModelFactory):
    class Meta:
        model = Etudiant
    
    universite = SubFactory(UniversiteFactory)
    user = SubFactory(UtilisateurFactory, role='etudiant')
    matricule = Sequence(lambda n: f'ETU{n:08d}')
    ine = Sequence(lambda n: f'{n:010d}A')
    date_naissance = Faker('date_of_birth', minimum_age=18, maximum_age=30)
    lieu_naissance = Faker('city', locale='fr_FR')
    sexe = factory.Iterator(['M', 'F'])
    nationalite = 'Française'
    adresse = Faker('address', locale='fr_FR')
    code_postal = Faker('postcode', locale='fr_FR')
    ville = Faker('city', locale='fr_FR')
    pays = 'France'
    telephone = Faker('phone_number', locale='fr_FR')
    statut = 'inscrit'
    regime = 'formation_initiale'


class InscriptionAdministrativeFactory(DjangoModelFactory):
    class Meta:
        model = InscriptionAdministrative
    
    etudiant = SubFactory(EtudiantFactory)
    annee_universitaire = SubFactory(AnneeUniversitaireFactory)
    formation = SubFactory(FormationFactory)
    date_inscription = Faker('date_this_year')
    statut = 'validee'


# =============================================================================
# INTÉGRATION LMS
# =============================================================================

class EdxUserMappingFactory(DjangoModelFactory):
    class Meta:
        model = EdxUserMapping
    
    user_sis = SubFactory(UtilisateurFactory)
    username_edx = Sequence(lambda n: f'edx_user_{n}')
    user_id_edx = Sequence(lambda n: 10000 + n)
    date_sync = LazyAttribute(lambda _: timezone.now())
    actif = True


class EdxCourseMappingFactory(DjangoModelFactory):
    class Meta:
        model = EdxCourseMapping
    
    ecue = SubFactory(ECUEFactory)
    course_id = Sequence(lambda n: f'course-v1:SIS+COURS{n:03d}+2026')
    course_name = Sequence(lambda n: f'Cours {n}')
    actif = True


class EdxEnrollmentFactory(DjangoModelFactory):
    class Meta:
        model = EdxEnrollment
    
    etudiant = SubFactory(EtudiantFactory)
    course = SubFactory(EdxCourseMappingFactory)
    enrollment_id = Sequence(lambda n: 50000 + n)
    is_active = True
    progression = 0


class OutboxEventFactory(DjangoModelFactory):
    class Meta:
        model = OutboxEvent
    
    event_type = 'user.sync'
    aggregate_type = 'user'
    aggregate_id = Sequence(lambda n: str(n))
    payload = {}
    statut = 'pending'
    nb_tentatives = 0
